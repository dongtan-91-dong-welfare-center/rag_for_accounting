"""docs/ 경로 인용 무결성 검사 — 온디맨드 유틸리티

문서가 인용하는 경로가 실재하는지 검사한다. "처음 온 사람이 클릭·탐색해서
길을 잃지 않는다"를 기계로 확인하는 도구다.

테스트 스위트에는 묶지 않는다(수동 실행). 문서 구조를 크게 손댄 뒤
`uv run python scripts/path_lint.py` 로 깨진 인용이 0인지 확인하는 용도.

추출 규약:

  스코프
    - docs/ 아래 모든 *.md + 루트 CLAUDE.md·README.md(있으면).
    - docs/archive/ 본문 제외(폐기 의도 보존). 단 docs/archive/README.md는
      포함 — 폐기 문서에서 현행으로 빠져나가는 리다이렉트 링크를 지키기 위함.
    - docs/superpowers/ 제외 — 역사적 plan·spec 기록이라 경로 신선도 비강제
      (삭제/이름변경/크로스브랜치 참조를 정확히 서술).

  ① 백틱 경로  `path/to/file.ext`
    - 공백 없음 + '/' 포함 + 알려진 확장자로 끝남 + '://' 없음일 때만 경로로 간주.
    - 셸 명령·모델 ID(nlpai-lab/KURE-v1)·git ref(origin/dev)·디렉터리는 걸러짐.
    - 해석 기준: 저장소 루트.

  ② 마크다운 링크  [text](target)
    - http(s)://·mailto:·#앵커는 건너뜀, #fragment·?query·"title"은 잘라냄.
    - 해석 기준: 문서가 위치한 디렉터리(상대 링크).

  코드펜스(``` ... ```) 내부는 추출 전 제거 — 트리 다이어그램 토큰 오탐 방지.
"""
from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

KNOWN_EXTS = (
    ".py", ".md", ".json", ".toml", ".yaml", ".yml", ".txt", ".sh",
    ".sql", ".xlsx", ".csv", ".svg", ".mmd", ".drawio", ".png", ".jpg",
    ".ipynb", ".cfg", ".ini", ".lock",
)
_PATH_CHARS = re.compile(r"[A-Za-z0-9_./-]+")


def _strip_fences(text: str) -> str:
    """코드펜스 블록을 줄 수 보존하며 제거(라인 번호 정합 유지)."""
    return re.sub(
        r"```.*?```",
        lambda m: "\n" * m.group(0).count("\n"),
        text,
        flags=re.DOTALL,
    )


def extract_refs(text: str) -> list[tuple[int, str, str]]:
    """문서 텍스트에서 경로 인용 추출 → [(lineno, kind, raw), ...]."""
    refs: list[tuple[int, str, str]] = []
    for lineno, line in enumerate(_strip_fences(text).splitlines(), 1):
        for span in re.findall(r"`([^`\n]+)`", line):
            s = span.strip()
            if (
                _PATH_CHARS.fullmatch(s)
                and "/" in s
                and "://" not in s
                and s.endswith(KNOWN_EXTS)
            ):
                refs.append((lineno, "backtick", s))
        for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", line):
            t = target.strip()
            if not t or t.startswith(("http://", "https://", "mailto:", "#")):
                continue
            t = t.split()[0].split("#", 1)[0].split("?", 1)[0]
            if t:
                refs.append((lineno, "link", t))
    return refs


def _resolve(kind: str, raw: str, doc_path: Path, repo_root: Path) -> Path:
    base = repo_root if kind == "backtick" else doc_path.parent
    return base / raw


def lint_file(doc_path: Path, repo_root: Path) -> list[tuple[int, str, str]]:
    text = doc_path.read_text(encoding="utf-8")
    return [
        (lineno, kind, raw)
        for lineno, kind, raw in extract_refs(text)
        if not _resolve(kind, raw, doc_path, repo_root).exists()
    ]


def iter_doc_files(repo_root: Path):
    docs = repo_root / "docs"
    if docs.is_dir():
        for p in sorted(docs.rglob("*.md")):
            rel = p.relative_to(docs)
            if rel.parts and rel.parts[0] == "archive" and p.name != "README.md":
                continue
            if rel.parts and rel.parts[0] == "superpowers":
                continue
            yield p
    for top in ("CLAUDE.md", "README.md"):
        p = repo_root / top
        if p.exists():
            yield p


def lint_docs(repo_root: Path = PROJECT_ROOT) -> list[tuple[str, int, str, str]]:
    broken: list[tuple[str, int, str, str]] = []
    for p in iter_doc_files(repo_root):
        for lineno, kind, raw in lint_file(p, repo_root):
            broken.append((str(p.relative_to(repo_root)), lineno, kind, raw))
    return broken


if __name__ == "__main__":
    result = lint_docs(PROJECT_ROOT)
    for rel, ln, kind, raw in result:
        print(f"  {rel}:{ln}  [{kind}] {raw}")
    print(f"\nTOTAL: {len(result)}")
