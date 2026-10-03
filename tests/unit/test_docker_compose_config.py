"""
tests/unit/test_docker_compose_config.py: docker-compose.yml 구문 및 TEI 기동 파라미터 무결성 테스트.

[배경 및 목적]
저사양 CPU 호스트(vCPU 2 / RAM 16GB 이하)에서 TEI 임베딩 컨테이너 기동 웜업 시
대용량 메모리 할당(OOM, exit 137)으로 인한 재시작 루프를 방지하기 위해,
배치 파라미터가 .env를 통해 올바르게 주입되어야 합니다.
또한 실제 데이터가 2,048토큰 이하임에 따라 조용한 절단(--auto-truncate) 옵션 및
TEI 1.8에서 지원되지 않는 --max-input-length 플래그가 배제되었는지 정적으로 검증합니다.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from src.utils import config

_ROOT = Path(__file__).resolve().parents[2]
_COMPOSE_FILE = _ROOT / "docker-compose.yml"


@pytest.mark.unit
class TestDockerComposeConfig:
    """docker-compose.yml 구성 파일의 정적 구문 및 TEI 설정 검증."""

    @pytest.fixture
    def compose_data(self) -> dict:
        """docker-compose.yml 파일을 YAML로 파싱하여 반환합니다."""
        assert _COMPOSE_FILE.exists(), f"docker-compose.yml 파일이 없습니다: {_COMPOSE_FILE}"
        with open(_COMPOSE_FILE, encoding="utf-8") as f:
            return yaml.safe_load(f)

    def test_docker_compose_loads_valid_yaml(self, compose_data):
        """docker-compose.yml이 유효한 YAML 구조를 갖추고 필수 서비스를 정의해야 합니다."""
        assert "services" in compose_data
        services = compose_data["services"]
        assert "database" in services
        assert "embedding" in services
        assert "app" in services

    def test_embedding_command_flags_and_defaults(self, compose_data):
        """embedding 서비스의 command에 필수 플래그와 기본값이 올바르게 지정되어야 합니다."""
        command = compose_data["services"]["embedding"]["command"]
        assert isinstance(command, list), "embedding command는 리스트 형식이어야 합니다."

        # 플래그 및 기본값 보간 문자열 확인
        # TODO: 모델 ID 환경변수화(EMBEDDING_MODEL) 시 pgvector 차원(EMBEDDING_DIM: 1024), DDL 마이그레이션 및 토크나이저 정합성 영향도를 함께 검토하여 연계 분리 필요
        assert "--model-id" in command
        model_idx = command.index("--model-id")
        assert command[model_idx + 1] == config.EMBEDDING_MODEL

        assert "--max-batch-tokens" in command
        batch_idx = command.index("--max-batch-tokens")
        assert command[batch_idx + 1] == "${TEI_MAX_BATCH_TOKENS:-8192}"

        assert not any("--max-input-length" in str(arg) for arg in command), (
            "--max-input-length 플래그는 TEI 1.8에서 지원되지 않아 크래시(exit 2)를 유발하므로 배제되어야 합니다."
        )

        compose_text = _COMPOSE_FILE.read_text(encoding="utf-8")
        assert "max_input_length" not in compose_text.lower(), (
            "max_input_length 관련 환경변수 및 플래그는 더 이상 지원되지 않으므로 docker-compose.yml에서 배제되어야 합니다."
        )
        assert "max-input-length" not in compose_text.lower(), (
            "max-input-length 플래그는 docker-compose.yml 전체(주석 및 설정 포함)에서 배제되어야 합니다."
        )

        assert "--max-client-batch-size" in command
        client_idx = command.index("--max-client-batch-size")
        assert command[client_idx + 1] == "${TEI_MAX_CLIENT_BATCH_SIZE:-8}"

    def test_embedding_healthcheck_wait_is_parameterized(self, compose_data):
        """arm64 에뮬레이션 웜업(약 9분)을 수용하도록 헬스체크 대기시간이 환경변수로 조정 가능해야 합니다."""
        hc = compose_data["services"]["embedding"]["healthcheck"]
        assert hc["start_period"] == "${TEI_HEALTH_START_PERIOD:-180s}"
        assert hc["retries"] == "${TEI_HEALTH_RETRIES:-60}"

    def test_embedding_command_excludes_auto_truncate(self, compose_data):
        """--auto-truncate 옵션은 적재 토큰 상한 규약(IX-201) 위반 및 품질 저하 은폐 방지를 위해 배제되어야 합니다."""
        command = compose_data["services"]["embedding"]["command"]
        assert not any("--auto-truncate" in str(arg) for arg in command), (
            "--auto-truncate 플래그가 포함되어 있습니다. 실데이터(2,047토큰) 보존을 위해 배제해야 합니다."
        )

    def test_app_raw_data_volume_includes_selinux_flag(self, compose_data):
        """Rocky/RHEL 환경(Podman)에서의 SELinux 권한 거부 방지를 위해 raw_data 마운트에 :ro,z 플래그가 있어야 합니다."""
        volumes = compose_data["services"]["app"]["volumes"]
        raw_data_mounts = [v for v in volumes if isinstance(v, str) and "./data/raw_data" in v]
        assert len(raw_data_mounts) == 1, "raw_data 볼륨 마운트가 정확히 1개 존재해야 합니다."
        assert raw_data_mounts[0] == "./data/raw_data:/app/data/raw_data:ro,z"

    def test_parameter_interpolation_resolution(self):
        """정규식을 활용해 .env 미지정 시 기본값(4096) 및 지정 시 오버라이드(8192) 치환을 검증합니다."""
        raw_content = _COMPOSE_FILE.read_text(encoding="utf-8")

        # 기본값 치환 헬퍼 (예: ${VAR:-DEFAULT})
        def resolve_defaults(text: str, env_overrides: dict[str, str] | None = None) -> str:
            env = env_overrides or {}
            def _repl(match: re.Match) -> str:
                var_name = match.group(1)
                default_val = match.group(2)
                val = env.get(var_name)
                # :- 구문은 변수가 미설정되었거나 빈 문자열("")일 때 기본값으로 치환합니다.
                return val if val else default_val
            return re.sub(r"\$\{([A-Za-z0-9_]+):-([^}]+)\}", _repl, text)

        # 1. 환경변수 없을 때 안전 기본값 치환 결과 (8192 / 8)
        resolved_default = yaml.safe_load(resolve_defaults(raw_content))
        default_cmd = resolved_default["services"]["embedding"]["command"]
        assert not any("max-input-length" in str(arg).lower() or "max_input_length" in str(arg).lower() for arg in default_cmd)
        assert default_cmd[default_cmd.index("--max-batch-tokens") + 1] == "8192"
        assert default_cmd[default_cmd.index("--max-client-batch-size") + 1] == "8"

        # 2. 고사양 호스트 오버라이드 결과 (16384 / 16)
        high_spec_env = {
            "TEI_MAX_BATCH_TOKENS": "16384",
            "TEI_MAX_CLIENT_BATCH_SIZE": "16",
        }
        resolved_high_spec = yaml.safe_load(resolve_defaults(raw_content, high_spec_env))
        high_spec_cmd = resolved_high_spec["services"]["embedding"]["command"]
        assert not any("max-input-length" in str(arg).lower() or "max_input_length" in str(arg).lower() for arg in high_spec_cmd)
        assert high_spec_cmd[high_spec_cmd.index("--max-batch-tokens") + 1] == "16384"   # ${TEI_MAX_BATCH_TOKENS:-16384}
        assert high_spec_cmd[high_spec_cmd.index("--max-client-batch-size") + 1] == "16"   # ${TEI_MAX_CLIENT_BATCH_SIZE:-16}

        # 3. 기존 서버 .env 잔존 레거시 변수(TEI_MAX_INPUT_LENGTH) 주입 시 하위 호환성 검증
        legacy_env = {
            "TEI_MAX_INPUT_LENGTH": "4096",
            "TEI_MAX_BATCH_TOKENS": "8192",
            "TEI_MAX_CLIENT_BATCH_SIZE": "8",
        }
        resolved_legacy = yaml.safe_load(resolve_defaults(raw_content, legacy_env))
        legacy_cmd = resolved_legacy["services"]["embedding"]["command"]
        assert not any("max-input-length" in str(arg).lower() or "max_input_length" in str(arg).lower() for arg in legacy_cmd)
        assert legacy_cmd[legacy_cmd.index("--max-batch-tokens") + 1] == "8192"
        assert legacy_cmd[legacy_cmd.index("--max-client-batch-size") + 1] == "8"

        # 4. 레거시 변수만 단독 주입되고 신규 변수가 미지정된 경우에도 안전 기본값(8192 / 8)으로 정상 해석
        legacy_only_env = {
            "TEI_MAX_INPUT_LENGTH": "9999",
        }
        resolved_legacy_only = yaml.safe_load(resolve_defaults(raw_content, legacy_only_env))
        legacy_only_cmd = resolved_legacy_only["services"]["embedding"]["command"]
        assert not any("max-input-length" in str(arg).lower() or "max_input_length" in str(arg).lower() for arg in legacy_only_cmd)
        assert legacy_only_cmd[legacy_only_cmd.index("--max-batch-tokens") + 1] == "8192"
        assert legacy_only_cmd[legacy_only_cmd.index("--max-client-batch-size") + 1] == "8"

        # 5. 환경변수가 빈 문자열("")로 전달되어도 Compose :- 구문에 따라 안전 기본값(8192 / 8)으로 정상 치환
        empty_env = {
            "TEI_MAX_BATCH_TOKENS": "",
            "TEI_MAX_CLIENT_BATCH_SIZE": "",
        }
        resolved_empty = yaml.safe_load(resolve_defaults(raw_content, empty_env))
        empty_cmd = resolved_empty["services"]["embedding"]["command"]
        assert not any("max-input-length" in str(arg).lower() or "max_input_length" in str(arg).lower() for arg in empty_cmd)
        assert empty_cmd[empty_cmd.index("--max-batch-tokens") + 1] == "8192"
        assert empty_cmd[empty_cmd.index("--max-client-batch-size") + 1] == "8"


