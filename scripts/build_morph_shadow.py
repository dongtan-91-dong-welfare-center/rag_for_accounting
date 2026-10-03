"""
배포 후보 셀을 운영 오염 없이 재기 위한 격리 지점.

[왜 그림자 테이블인가] 재려는 것은 "형태소 사전토큰화 + ts_rank_cd(IDF 없음)"이다 —
현행 스택에서 인프라 추가 없이 배포 가능한 유일한 sparse 구성이다. 
그런데 이 구성은 본문을 미리 형태소로 쪼개 저장해야 하므로 스키마 변경이 필요하다.
측정 전에 운영 chunks를 바꾸면 셀이 기각됐을 때 되돌려야 하므로, 같은 chunk_id를 가진 사본 테이블에만 컬럼을 만든다.
searcher.sparse_search의 collection 주입점과 같은 격리 규약이다.

[왜 컬럼이 3개인가] 품사 필터의 순효과를 가르기 위해서다. 
ts_rank_cd에는 IDF가 없어서 흔한 형태소가 자동 감쇠되지 않으므로(오프라인 BM25와 다른 점), 저IDF 노이즈를 걷어내는 수단은 품사 필터뿐이다.
다만 어근·접사(XR·XSN)를 남길지가 결과를 좌우하므로 실측으로 가른다.
  morph_all  — 필터 없음(조사·어미 포함). 대조군: 필터가 정말 필요한지 반증한다.
  morph_core — 순수 명사류(NNG·NNP·SL·SN·SH)
  morph_wide — CORE + 어근·접사(XR·XSN·XPN). "환입액"→환/입/액의 "환"(XR)이 여기서만 남는다

[제약] 운영 chunks는 읽기만 한다. embedding 컬럼은 복제하지 않는다.
dense는 운영 테이블에서 돌고 chunk_id로 대응되므로 그림자 쪽에 벡터가 필요 없다.

사용 (호스트 실행, DB 기동·chunks 적재 전제 — kiwipiepy는 dev 그룹이라 uv run에 기본 포함):
  uv run python scripts/build_morph_shadow.py
  uv run python scripts/build_morph_shadow.py --drop   # 측정 후 정리
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from psycopg import sql  # noqa: E402

from src.utils.config import (  # noqa: E402
    CHUNKS_TABLE,
    MORPH_CHUNKS_TABLE,
    MORPH_POS_TAGS_CORE,
    MORPH_POS_TAGS_WIDE,
)

# 사전토큰화 컬럼 → 그 컬럼에 적용할 품사 화이트리스트(None=필터 없음).
# 하니스(sparse_morph_replay)가 이 딕셔너리를 그대로 arm 축으로 쓴다.
MORPH_COLUMNS: dict[str, tuple[str, ...] | None] = {
    "morph_all": None,
    "morph_core": MORPH_POS_TAGS_CORE,
    "morph_wide": MORPH_POS_TAGS_WIDE,
}

# UPDATE 배치 크기 — 1500청크 규모에서 왕복을 줄이되 파라미터 상한에 걸리지 않는 값.
UPDATE_BATCH = 200


def _drop(cur) -> None:
    """그림자 테이블을 지운다(측정 후 정리 · 재빌드 전 초기화)."""
    cur.execute(sql.SQL("DROP TABLE IF EXISTS {t}").format(t=sql.Identifier(MORPH_CHUNKS_TABLE)))


def _create(cur) -> int:
    """
    운영 chunks에서 채점에 필요한 컬럼만 복제하고 사전토큰화 컬럼을 추가한다.

    content(원문)를 그대로 들고 오는 이유: 채점이 청크 본문에서 조항 번호를 추출하므로 검색 결과는 원문을 돌려줘야 한다.
    매칭만 morph_* 컬럼에서 하고 반환은 content로 한다.
    """
    cur.execute(
        sql.SQL(
            "CREATE TABLE {t} AS SELECT chunk_id, document_id, content, metadata FROM {src}"
        ).format(t=sql.Identifier(MORPH_CHUNKS_TABLE), src=sql.Identifier(CHUNKS_TABLE))
    )
    for column in MORPH_COLUMNS:
        cur.execute(
            sql.SQL("ALTER TABLE {t} ADD COLUMN {c} text").format(
                t=sql.Identifier(MORPH_CHUNKS_TABLE), c=sql.Identifier(column)
            )
        )
    cur.execute(sql.SQL("SELECT count(*) FROM {t}").format(t=sql.Identifier(MORPH_CHUNKS_TABLE)))
    return int(cur.fetchone()[0])


def _tokenize_rows(cur) -> None:
    """
    본문을 컬럼별 화이트리스트로 형태소 토큰화해 채운다.

    운영 검색이 쓸 morph_text()를 그대로 호출한다
    색인 토큰과 질의 토큰이 같은 함수를 통과하지 않으면 매칭이 조용히 깨지므로, 이 공유가 측정의 전제다.
    """
    from src.retrieval.tokenizer import morph_text

    cur.execute(
        sql.SQL("SELECT chunk_id, content FROM {t} ORDER BY chunk_id").format(
            t=sql.Identifier(MORPH_CHUNKS_TABLE)
        )
    )
    rows = cur.fetchall()

    set_clause = sql.SQL(", ").join(
        sql.SQL("{c} = %s").format(c=sql.Identifier(column)) for column in MORPH_COLUMNS
    )
    update_sql = sql.SQL("UPDATE {t} SET {sets} WHERE chunk_id = %s").format(
        t=sql.Identifier(MORPH_CHUNKS_TABLE), sets=set_clause
    )

    t0 = time.perf_counter()
    batch: list[list] = []
    for i, (chunk_id, content) in enumerate(rows, start=1):
        params = [morph_text(content, tags) for tags in MORPH_COLUMNS.values()]
        batch.append(params + [chunk_id])
        if len(batch) >= UPDATE_BATCH or i == len(rows):
            cur.executemany(update_sql, batch)
            batch = []
            print(f"  토큰화 {i}/{len(rows)} ({time.perf_counter() - t0:.1f}s)")


def _index(cur) -> None:
    """
    컬럼별 GIN 인덱스 — to_tsvector 표현식 인덱스.

    운영 sparse_search는 인덱스 없이 매 행 to_tsvector(content)를 계산해 순차 스캔한다.
    사전토큰화 컬럼에 표현식 인덱스를 걸면 이 비용도 함께 사라진다
    형태소로 매칭이 살아나면 반환 행이 늘어나므로 인덱스 없이는 지연이 더 나빠진다.
    """
    for column in MORPH_COLUMNS:
        cur.execute(
            sql.SQL(
                "CREATE INDEX {idx} ON {t} USING GIN (to_tsvector('simple', {c}))"
            ).format(
                idx=sql.Identifier(f"{MORPH_CHUNKS_TABLE}_{column}_gin"),
                t=sql.Identifier(MORPH_CHUNKS_TABLE),
                c=sql.Identifier(column),
            )
        )
        print(f"  GIN 인덱스: {column}")


def _sample(cur) -> None:
    """토큰화 결과 1건을 눌러 보여 준다 — 화이트리스트가 의도대로 걸렸는지 눈으로 확인하는 용도."""
    cur.execute(
        sql.SQL("SELECT content, {cols} FROM {t} ORDER BY chunk_id LIMIT 1").format(
            cols=sql.SQL(", ").join(sql.Identifier(c) for c in MORPH_COLUMNS),
            t=sql.Identifier(MORPH_CHUNKS_TABLE),
        )
    )
    row = cur.fetchone()
    if not row:
        return
    print(f"\n표본 (원문 앞 60자): {row[0][:60]}...")
    for column, value in zip(MORPH_COLUMNS, row[1:]):
        print(f"  {column:<11}: {(value or '')[:90]}...")


def run(drop_only: bool) -> int:
    """그림자 테이블을 빌드한다(--drop이면 정리만 하고 끝낸다)."""
    # 호스트 실행 시 DB 호스트 보정 (다른 하니스와 동일 규약)
    if os.getenv("POSTGRES_HOST") == "database":
        os.environ["POSTGRES_HOST"] = "localhost"

    from src.db.connection import init_pool, close_pool, get_pool

    init_pool()
    try:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                if drop_only:
                    _drop(cur)
                    print(f"그림자 테이블 삭제: {MORPH_CHUNKS_TABLE}")
                    return 0

                _drop(cur)
                n = _create(cur)
                print(f"그림자 테이블 생성: {MORPH_CHUNKS_TABLE} · {n}청크 · 컬럼 {list(MORPH_COLUMNS)}")
                _tokenize_rows(cur)
                _index(cur)
                _sample(cur)
                print(f"\n완료 — scripts/sparse_morph_replay.py로 측정한다.")
    finally:
        close_pool()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="형태소 사전토큰화 그림자 테이블 빌드")
    parser.add_argument("--drop", action="store_true", help="그림자 테이블만 삭제하고 종료(측정 후 정리)")
    return parser


def main(argv: list[str] | None = None) -> int:
    return run(build_parser().parse_args(argv).drop)


if __name__ == "__main__":
    raise SystemExit(main())
