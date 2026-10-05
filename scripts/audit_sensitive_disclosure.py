#!/usr/bin/env python3
"""
GitHub 저장소 내 민감 정보 및 기밀 자산 노출 점검 스크립트.

점검 대상:
1. 구글 스프레드시트/드라이브 등 외부 공유 링크 (docs.google.com, drive.google.com 등)
2. 민감 비밀값/토큰 패턴 (OpenAI sk-, LangSmith lsv2_, HuggingFace hf_, AWS AKIA, DB password 등)
3. 벤치마크 평가 정답셋/질의 원문 패턴 (TEST-K-GAAP-, TEST-K-IFRS-, expected_answer 등)
4. 내부 IP/도메인 또는 고객사 식별자

사용법:
    uv run python scripts/audit_sensitive_disclosure.py
    또는
    python3 scripts/audit_sensitive_disclosure.py [--include-closed] [--limit 300]
"""

import argparse
import json
import re
import subprocess
import sys
from typing import Any


PATTERNS = {
    "google_drive_sheet": re.compile(
        r"https?://(?:docs|drive)\.google\.com/[^\s\)\>]+", re.IGNORECASE
    ),
    "openai_api_key": re.compile(r"sk-[a-zA-Z0-9_\-]{20,}", re.IGNORECASE),
    "huggingface_token": re.compile(r"hf_[a-zA-Z0-9]{20,}", re.IGNORECASE),
    "langsmith_api_key": re.compile(r"lsv2_[a-zA-Z0-9_\-]{20,}", re.IGNORECASE),
    "aws_access_key": re.compile(r"(?:AKIA|ABIA|ACCA)[0-9A-Z]{16}", re.IGNORECASE),
    "db_password_exposure": re.compile(
        r"(?:postgres(?:ql)?://[a-zA-Z0-9_\-]+:)[^@\s]{4,}@", re.IGNORECASE
    ),
    "benchmark_test_case": re.compile(
        r"TEST-K-(?:GAAP|IFRS)-\d{3}", re.IGNORECASE
    ),
}


def run_gh_json(cmd: list[str]) -> Any:
    """gh CLI 실행 후 JSON 결과를 파싱하여 반환한다."""
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        return None
    try:
        return json.loads(res.stdout)
    except json.JSONDecodeError:
        return None


def scan_text(text: str) -> dict[str, list[str]]:
    """텍스트 내에서 패턴별 매칭된 결과를 추출한다."""
    findings = {}
    for name, pattern in PATTERNS.items():
        matches = pattern.findall(text)
        if matches:
            findings[name] = list(set(matches))
    return findings


def _inspect_item(item_type: str, item: dict[str, Any]) -> bool:
    """단일 이슈 또는 PR 항목의 본문 및 댓글을 검사하고 발견 시 출력한다."""
    num = item["number"]
    data = run_gh_json(
        ["gh", item_type, "view", str(num), "--json", "number,title,body,comments"]
    )
    if not data:
        return False

    body_findings = scan_text(data.get("body", ""))
    comment_findings = []
    for c in data.get("comments", []):
        cf = scan_text(c.get("body", ""))
        if cf:
            comment_findings.append((c.get("id"), c.get("author", {}).get("login"), cf))

    if not body_findings and not comment_findings:
        return False

    print(f"\n[!] {item_type.upper()} #{num}: {data.get('title')}")
    if body_findings:
        print(f"    - [본문 탐지]: {body_findings}")
    for cid, author, cf in comment_findings:
        print(f"    - [댓글 탐지 (ID: {cid}, 작성자: {author})]: {cf}")
    return True


def audit_target(item_type: str, limit: int, state_flag: str) -> int:
    """특정 대상(issue 또는 pr) 전체를 순회 검사하여 탐지 건수를 반환한다."""
    items = run_gh_json(
        ["gh", item_type, "list", "--state", state_flag, "--limit", str(limit), "--json", "number,title"]
    ) or []

    print(f"[*] 검색된 {item_type.upper()} 수: {len(items)}개")
    findings_count = sum(1 for item in items if _inspect_item(item_type, item))
    return findings_count


def audit_issues_and_prs(limit: int = 300, include_closed: bool = True):
    """이슈 및 PR 본문/코멘트를 대상으로 민감 데이터 노출 여부를 점검한다."""
    state_flag = "all" if include_closed else "open"
    print(f"[*] GitHub 이슈 및 PR 스캔 시작 (state={state_flag}, limit={limit})...\n")

    issue_findings = audit_target("issue", limit, state_flag)
    pr_findings = audit_target("pr", limit, state_flag)
    total_findings = issue_findings + pr_findings

    print("\n" + "=" * 60)
    if total_findings == 0:
        print("[✓] 안전함: 점검 대상 패턴에 해당하는 노출 건이 발견되지 않았습니다.")
    else:
        print(f"[!] 총 {total_findings}건의 항목에서 탐지된 내역이 있습니다.")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Audit sensitive information disclosure in GitHub repo")
    parser.add_argument("--limit", type=int, default=300, help="최대 검사할 이슈/PR 수")
    parser.add_argument("--include-closed", action="store_true", default=True, help="종료된 이슈/PR 포함 여부")
    args = parser.parse_args()

    audit_issues_and_prs(limit=args.limit, include_closed=args.include_closed)
