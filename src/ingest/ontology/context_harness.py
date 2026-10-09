"""
청크 문맥 보존 여부 점검 하네스

## 배경
검색 실패 원인이 청킹 경계에 있는지 검색 알고리즘에 있는지를 판별하기 위해,
원문 청크를 자동으로 검사해 문맥 단절 여부를 분류하는 하네스를 제공한다.

## 검사 항목
1. **문장 경계 단절** (``sentence_boundary``): 청크 끝이 문장 완결 기호(마침표·물음표·느낌표 등)
   없이 끊겼는지 확인한다. 문장 완결 없이 끝나는 청크는 다음 청크와의 경계에서 문맥이 잘렸을
   가능성이 높다.
2. **조항 번호 연속성** (``clause_number_gap``): ``clause_level=True``로 분할된 청크 시퀀스에서
   조항 헤더(``#### N.N``) 번호가 연속적으로 이어지는지 확인한다. 번호가 뛰어 넘겨지면 일부
   조항이 청크에서 누락됐을 수 있다.

## 출력 형식
각 검사 케이스는 ``ContextCheckResult``(schemas.py SSoT)로 반환된다.
``run_context_harness``는 모든 검사를 실행하고 결과 리스트를 반환한다.

## 비범위
청킹 로직 자체의 수정은 이 하네스의 판정 결과가 나온 뒤 별도 이슈에서 다룬다.
LLM 에이전트 기반 판정 위임은 후속 이슈에서 이 하네스를 기반으로 확장한다.
"""
import logging
import re
from collections.abc import Sequence

from src.models.schemas import ContextCheckResult, RetrievedChunk
from src.utils.logger import get_logger, log_kv

logger = get_logger(__name__)

# 문장 완결 기호 — 한글·영문 마침표·물음표·느낌표(전각 포함) 및 닫는 괄호로 끝나는 경우를 포함한다.
# 닫는 인용 부호나 괄호 뒤에 마침표가 오는 경우도 완결로 처리한다.
_SENTENCE_END_RE = re.compile(r"[.。!?！？\"'”’)\]）」』]\s*$")

# 조항 헤더 — 청크 첫 줄에서 "#### N.N" 형식을 잡는다.
# N.N은 정수점 정수(예: 21.8) 또는 가지번호(예: 21.5의2)를 허용한다.
_CLAUSE_HEADER_RE = re.compile(r'^#{1,6}\s+(\d+\.\d+(?:의\d+)?)', re.MULTILINE)


def detect_broken_sentences(chunks: Sequence[RetrievedChunk]) -> list[ContextCheckResult]:
    """
    각 청크 끝이 문장 경계에서 완결됐는지 검사한다.

    마지막 청크를 제외한 청크(중간 경계가 있는 위치)에 대해 검사를 수행한다.
    마지막 청크는 원문 자체의 끝이므로 경계 단절 여부 판정 대상이 아니다.

    :param chunks: 검사할 ``RetrievedChunk`` 시퀀스. 동일 노드에서 나온 분할 청크이거나
                   문서 전체 청크 목록일 수 있다.
    :return: 청크별 ``ContextCheckResult`` 리스트 (``check_type="sentence_boundary"``).
    """
    results: list[ContextCheckResult] = []
    # 마지막 청크는 문서 또는 노드의 자연스러운 끝이므로 검사 대상에서 제외한다.
    boundary_chunks = list(chunks)[:-1]
    for chunk in boundary_chunks:
        tail = chunk.content.rstrip()
        passed = bool(_SENTENCE_END_RE.search(tail))
        if passed:
            detail = f"청크 끝이 문장 완결 기호로 종료됨: ...{tail[-30:]!r}"
        else:
            # 마지막 20자를 근거로 제시해 판정 근거를 명확히 한다.
            snippet = tail[-40:] if len(tail) > 40 else tail
            detail = (
                f"문장 미완결 의심 — 청크 끝 텍스트가 문장 종결 기호 없이 끝남: ...{snippet!r}"
            )
        results.append(
            ContextCheckResult(
                chunk_id=chunk.chunk_id,
                check_type="sentence_boundary",
                passed=passed,
                detail=detail,
            )
        )
    log_kv(
        logger, logging.DEBUG, "ingest", "문장 경계 검사 완료",
        건수=len(results), 의심건수=sum(1 for r in results if not r.passed),
    )
    return results


def _extract_clause_number(text: str) -> tuple[int, int, int | None] | None:
    """
    청크 첫 번째 조항 헤더(#### N.N 또는 #### N.N의M)에서 숫자 튜플을 추출한다.

    :return: (major, minor, branch) 또는 헤더가 없으면 None.
             branch는 가지번호(의N) 존재 시 정수, 없으면 None.
    """
    m = _CLAUSE_HEADER_RE.search(text)
    if not m:
        return None
    raw = m.group(1)  # 예: "21.8" 또는 "21.5의2"
    if "의" in raw:
        main, branch_str = raw.split("의", 1)
        major_str, minor_str = main.split(".", 1)
        return int(major_str), int(minor_str), int(branch_str)
    major_str, minor_str = raw.split(".", 1)
    return int(major_str), int(minor_str), None


def detect_clause_number_gaps(chunks: Sequence[RetrievedChunk]) -> list[ContextCheckResult]:
    """
    연속된 청크 사이에서 조항 번호 갭(누락)을 감지한다.

    조항 헤더(``#### N.N``)가 있는 청크 쌍을 순서대로 비교해, 번호가 1 초과로 뛰면
    갭(조항 누락 의심)으로 판정한다.

    가지번호(21.5의2)는 21.5와 21.6 사이의 정상 삽입으로 처리하며, 가지번호 자체 사이의
    갭(21.5의1 → 21.5의3)도 감지한다.

    :param chunks: 검사할 청크 시퀀스. ``clause_level=True`` 분할 결과를 넣는 것이 전제이다.
    :return: 갭 경계가 있는 청크 쌍에 대한 ``ContextCheckResult`` 리스트
             (``check_type="clause_number_gap"``).
    """
    results: list[ContextCheckResult] = []
    # 조항 헤더가 있는 청크만 추려 순서를 보존한다.
    clause_chunks = [(c, _extract_clause_number(c.content)) for c in chunks]
    clause_chunks = [(c, num) for c, num in clause_chunks if num is not None]

    for i in range(len(clause_chunks) - 1):
        cur_chunk, cur_num = clause_chunks[i]
        next_chunk, next_num = clause_chunks[i + 1]
        assert cur_num is not None and next_num is not None  # 위에서 필터링했으므로 항상 참

        cur_major, cur_minor, cur_branch = cur_num
        next_major, next_minor, next_branch = next_num

        # 장(major)이 다르면 장 전환이므로 갭 판정 대상이 아니다.
        if cur_major != next_major:
            continue

        passed: bool
        detail: str

        if cur_branch is None and next_branch is None:
            # 일반 조항(21.8 → 21.9): minor 차이가 1이면 정상 연속이다.
            gap = next_minor - cur_minor
            if gap <= 1:
                passed = True
                detail = (
                    f"{cur_major}.{cur_minor} → {next_major}.{next_minor}: "
                    "조항 번호가 연속적으로 이어짐."
                )
            else:
                passed = False
                detail = (
                    f"{cur_major}.{cur_minor} → {next_major}.{next_minor}: "
                    f"조항 번호가 {gap - 1}개 뛰어 넘겨짐 — 중간 조항 누락 의심."
                )
        elif cur_branch is None and next_branch is not None:
            # 일반 조항 다음에 가지번호 등장: minor가 같아야 한다(21.5 → 21.5의2).
            if next_minor == cur_minor:
                passed = True
                detail = (
                    f"{cur_major}.{cur_minor} → {next_major}.{next_minor}의{next_branch}: "
                    "가지번호 삽입 — 정상 연속."
                )
            else:
                passed = False
                detail = (
                    f"{cur_major}.{cur_minor} → {next_major}.{next_minor}의{next_branch}: "
                    "가지번호 minor가 이전 조항과 다름 — 구조 이상 의심."
                )
        elif cur_branch is not None and next_branch is None:
            # 가지번호 다음에 일반 조항: minor가 1 증가해야 한다(21.5의2 → 21.6).
            gap = next_minor - cur_minor
            if gap <= 1:
                passed = True
                detail = (
                    f"{cur_major}.{cur_minor}의{cur_branch} → {next_major}.{next_minor}: "
                    "가지번호 종료 후 정상 연속."
                )
            else:
                passed = False
                detail = (
                    f"{cur_major}.{cur_minor}의{cur_branch} → {next_major}.{next_minor}: "
                    f"가지번호 종료 후 번호가 {gap - 1}개 뛰어 넘겨짐 — 누락 의심."
                )
        else:
            # 가지번호 → 가지번호: minor가 같고 branch가 1 증가해야 한다.
            assert cur_branch is not None and next_branch is not None
            if cur_minor == next_minor and next_branch - cur_branch == 1:
                passed = True
                detail = (
                    f"{cur_major}.{cur_minor}의{cur_branch} → "
                    f"{next_major}.{next_minor}의{next_branch}: 가지번호 연속."
                )
            else:
                passed = False
                detail = (
                    f"{cur_major}.{cur_minor}의{cur_branch} → "
                    f"{next_major}.{next_minor}의{next_branch}: "
                    "가지번호 사이 갭 또는 minor 불일치 — 구조 이상 의심."
                )

        results.append(
            ContextCheckResult(
                chunk_id=next_chunk.chunk_id,
                check_type="clause_number_gap",
                passed=passed,
                detail=detail,
            )
        )

    log_kv(
        logger, logging.DEBUG, "ingest", "조항 번호 연속성 검사 완료",
        건수=len(results), 의심건수=sum(1 for r in results if not r.passed),
    )
    return results


def run_context_harness(chunks: Sequence[RetrievedChunk]) -> list[ContextCheckResult]:
    """
    모든 문맥 보존 검사를 실행하고 케이스별 근거 포함 리포트를 반환한다.

    현재 포함된 검사:
    - 문장 경계 단절 검사 (``detect_broken_sentences``)
    - 조항 번호 연속성 갭 검사 (``detect_clause_number_gaps``)

    :param chunks: 검사할 ``RetrievedChunk`` 시퀀스.
    :return: 모든 검사의 ``ContextCheckResult`` 리스트.
             단절 없음이면 ``passed=True``, 단절 의심이면 ``passed=False``.
    """
    results: list[ContextCheckResult] = []
    results.extend(detect_broken_sentences(chunks))
    results.extend(detect_clause_number_gaps(chunks))
    total = len(results)
    broken = sum(1 for r in results if not r.passed)
    log_kv(
        logger, logging.INFO, "ingest", "문맥 보존 하네스 완료",
        건수=total, 의심건수=broken, 통과건수=total - broken,
    )
    return results


def render_report_markdown(results: Sequence[ContextCheckResult]) -> str:
    """
    점검 결과를 ``docs/benchmark/`` 산출물과 같은 형식(케이스별 근거 포함)의 마크다운으로 변환한다.

    근거: 이슈 #298이 판정 결과를 케이스별 근거가 포함된 리포트로 남기도록 요구한다.

    :param results: ``run_context_harness`` 가 반환한 결과 리스트.
    :return: 요약 표와 케이스별 근거 표를 담은 마크다운 문자열.
    """
    total = len(results)
    broken = [r for r in results if not r.passed]
    lines = [
        "# 청크 문맥 보존 점검 리포트",
        "",
        f"- 총 검사: {total}건",
        f"- 단절 의심: {len(broken)}건",
        f"- 통과: {total - len(broken)}건",
        "",
        "| 청크 ID | 검사 유형 | 판정 | 근거 |",
        "|---|---|---|---|",
    ]
    for r in results:
        verdict = "통과" if r.passed else "단절 의심"
        detail = r.detail.replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {r.chunk_id} | {r.check_type} | {verdict} | {detail} |")
    return "\n".join(lines) + "\n"
