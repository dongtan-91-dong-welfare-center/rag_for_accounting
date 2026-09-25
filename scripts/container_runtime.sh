#!/usr/bin/env bash
# 컨테이너 런타임 판정: install.sh·check.sh·db_dump.sh·db_restore.sh가 source로 함께 읽습니다.
#
# [배경]
# 이 저장소의 스택은 compose 파일 하나로 뜨지만, compose를 실행하는 명령은 환경마다 다르다.
# 개발자 노트북은 대개 Docker Compose v2가 깔려 있어 `docker compose`가 그대로 동작한다.
# 반면 Rocky·RHEL 계열 서버의 기본 컨테이너 런타임은 Podman이고, Podman에는 오랫동안 compose에 해당하는 하위 명령이 없었다.
# `podman-docker`(docker라는 이름의 명령을 podman으로 바꿔치기하는 얇은 래퍼) 패키지를 깔아도 사정은 같아서,
# `docker compose up -d`가 `podman compose up -d`로 넘어가며 `-d`를 최상위 플래그로 오인하고 즉시 죽는다.
#
# [목적]
# 어느 명령으로 compose를 부를지, 어느 명령으로 컨테이너를 들여다볼지를 한 곳에서 정한다.
# 네 스크립트가 각자 판정하면 한 곳만 고치는 실수가 생기기 때문이다.
#
# [쓰는 법]
#   source "$ROOT/scripts/container_runtime.sh"
#   detect_container_runtime || { container_runtime_hint; exit 1; }
#   "${COMPOSE[@]}" up "${COMPOSE_UP_FLAGS[@]}"
#   "${CONTAINER[@]}" exec accounting_db psql -U accounting_user -d accounting_db -c '\dt'
#
# [왜 문자열이 아니라 배열인가]
# `docker compose`는 두 낱말이다.
# COMPOSE="docker compose"처럼 문자열에 담고 "$COMPOSE" up으로 부르면 셸이 "docker compose"라는 이름의 실행 파일 하나를 찾다가 실패한다. 
# 따옴표를 빼면 이번에는 값에 공백이 들어간 다른 상황에서 예기치 않게 쪼개진다. 배열로 두면 두 경우가 모두 없다.

# podman-compose로 스택을 올릴 때 붙이는 인자다.
# `--force-recreate`가 왜 필요한지는 이렇다.
# podman-compose는 이미지를 새로 구워도, compose 파일 자체가 그대로면 이미 있는 컨테이너를 지우지 않고 그냥 다시 시작한다.
# 그래서 코드를 고치고 다시 올려도 옛 이미지가 계속 돈다.
# 배포한 사람은 성공했다고 보는데 바뀐 코드는 실행되지 않는, 알아차리기 쉬운 실패다.
# 이 동작은 podman-compose 1.0.6(Rocky 8의 EPEL 패키지)에서 확인했고
# 상위 저장소의 수정 커밋이 아직 어느 배포판에도 실리지 않아 최신 버전에서도 같다.
# Docker Compose v2에는 없는 문제이므로 그쪽에는 붙이지 않는다.
# 붙이면 멀쩡한 컨테이너를 매번 지웠다 만들어 불필요한 중단이 생긴다.
_COMPOSE_UP_FLAGS_PODMAN=(-d --build --force-recreate)

# compose 실행 방식과 컨테이너 조작 명령을 정한다.
# 찾았으면 0, 아무것도 못 찾았으면 1을 돌려준다.
detect_container_runtime() {
  local version_output=""

  # 1. 순수 Docker Compose v2 확인
  # 기존 Docker 사용자의 동작이 그대로 유지되어야 하므로 Docker를 가장 먼저 확인합니다.
  # 근거: Podman 4.4.x 환경의 podman-docker 래퍼는 compose 서브커맨드가 없음에도
  # 에러 메시지를 stderr로만 내보내고 종료 코드 0을 반환하거나 빈 출력을 생성할 수 있습니다.
  # 따라서 단순 종료 코드 0만으로 판정하지 않고, stdout 출력에 "Docker Compose" 식별자가 포함되어 있으며
  # podman 관련 문자열이 섞여 있지 않은 순수 Docker Compose v2 환경인지 명시적으로 검증합니다.
  if version_output="$(docker compose version 2>/dev/null)"; then
    case "$version_output" in
      *"Docker Compose"*)
        case "$version_output" in
          *podman*|*Podman*) ;;
          *)
            COMPOSE=(docker compose)
            CONTAINER=(docker)
            COMPOSE_UP_FLAGS=(-d --build)
            return 0
            ;;
        esac
        ;;
    esac
  fi

  # 2. podman-compose 확인
  # Rocky Linux 및 RHEL 계열 서버의 Podman 환경에서는 podman-compose를 직접 호출하는 방식이 가장 안전합니다.
  # 근거: podman-docker 래퍼를 거쳐 `docker compose up -d`를 호출하면 `podman compose up -d`로 넘어가면서
  # Podman 4.4.x에서 최상위 플래그 파싱 에러(unknown shorthand flag: 'd' in -d)가 발생하므로 직접 호출해야 합니다.
  if command -v podman-compose >/dev/null 2>&1; then
    COMPOSE=(podman-compose)
    COMPOSE_UP_FLAGS=("${_COMPOSE_UP_FLAGS_PODMAN[@]}")
    # ps·exec·inspect는 podman을 직접 부릅니다.
    # 래퍼를 거치면 환경에 따라 안내 문구가 함께 나와서 출력을 파싱하는 자리에서 걸릴 수 있습니다.
    # podman 명령이 없는 환경이라면 래퍼라도 씁니다.
    if command -v podman >/dev/null 2>&1; then
      CONTAINER=(podman)
    else
      CONTAINER=(docker)
    fi
    return 0
  fi

  # 3. Podman 4.7+ 외부 compose 위임 환경 (podman-compose가 PATH에 직접 노출되지 않은 특수 환경)
  # Podman 4.7부터 생긴 compose 하위 명령이 동작하여 버전 출력에 podman이 남는 경우입니다.
  # 근거 1 (COMPOSE 배정 사유): `docker compose version`이 성공하고 출력에 podman이 포함된 것은,
  # 시스템의 Podman이 docker compose 명령을 가로채서 외부 compose 공급자로 정상 위임하고 있음을 의미합니다.
  # 따라서 compose 실행 명령은 동작이 이미 검증된 `docker compose`를 그대로 채택합니다.
  # 단, 외부 공급자를 거치더라도 컨테이너 재생성 문제는 동일하게 발생하므로 --force-recreate 플래그를 지정합니다.
  # 근거 2 (CONTAINER 배정 사유 및 폴백): case 조건이 podman임에도 CONTAINER 기본값을 docker로 고정하면,
  # 컨테이너 조작 시 podman-docker 래퍼를 거치며 매번 stderr 안내 문구(Emulate Docker CLI...)가 출력되어 파싱 오류를 유발합니다.
  # 따라서 시스템에 네이티브 `podman` 명령어가 존재하면 `CONTAINER=(podman)`을 우선 배정합니다.
  # 만약 podman 바이너리가 PATH에 없고 docker 래퍼만 노출된 특수 환경이라면 불가피하게 `CONTAINER=(docker)`로 폴백합니다.
  case "$version_output" in
    *podman*|*Podman*)
      COMPOSE=(docker compose)
      if command -v podman >/dev/null 2>&1; then
        CONTAINER=(podman)
      else
        CONTAINER=(docker)
      fi
      COMPOSE_UP_FLAGS=("${_COMPOSE_UP_FLAGS_PODMAN[@]}")
      return 0
      ;;
  esac

  # 4. 아무것도 찾지 못한 경우
  # 판정에 실패해도 세 배열을 비우지는 않습니다.
  # `set -u`가 켜진 셸에서 빈 배열을 "${COMPOSE[@]}"로 펼치면 bash 4.4 미만(macOS 기본 3.2 포함)이 "unbound variable" 오류를 내며 종료됩니다.
  # 호출한 쪽이 실패를 사용자에게 알리고 나머지 점검을 이어 갈 수 있도록 안전한 기본값을 남깁니다.
  COMPOSE=(docker compose)
  CONTAINER=(docker)
  COMPOSE_UP_FLAGS=(-d --build)
  return 1
}

# 무엇을 설치해야 하는지 알려 준다.
# 표준 출력이 아니라 표준 오류로 내보내, 명령 결과를 파이프로 받아 쓰는 자리에 섞이지 않게 한다.
# cat 대신 셸에 내장된 printf를 쓰는 이유는, 이 안내가 나와야 하는 상황이 곧 환경이 온전치 않은 상황이기 때문이다.
# 외부 명령에 기대지 않으면 PATH가 망가진 환경에서도 안내는 출력된다.
container_runtime_hint() {
  printf '%s\n' >&2 \
    "compose를 지원하는 컨테이너 런타임을 찾을 수 없습니다. 아래 중 하나를 설치해 주세요." \
    "" \
    "  Docker Compose v2 (macOS, Windows, most Linux desktops)" \
    "    https://docs.docker.com/compose/install/" \
    "" \
    "  podman-compose (Rocky Linux, RHEL, AlmaLinux)" \
    "    podman-compose는 기본 저장소에 포함되어 있지 않으므로 EPEL을 먼저 활성화하세요." \
    "    sudo dnf install -y epel-release" \
    "    sudo dnf install -y podman podman-compose"
}
