"""
운영 chunks에 content_morph(형태소 사전토큰화 사본)를 백필한다.

[왜 필요한가] sparse 검색이 content_morph 컬럼에서 형태소 매칭을 하도록 전환됐다.
신규 적재는 색인 경로가 컬럼을 자동으로 채우지만,채택 이전에 적재된 기존 청크는 값이 비어 있다.
비어 있으면 sparse가 그 청크를 조용히 건너뛰어 버려 하이브리드 검색이 사실상 dense 단독 검색이 되어버린다.

[하는 일] 파싱·임베딩은 그대로 두고 UPDATE만 한다.
content가 불변이므로 전체 재적재가 필요 없다. 컬럼·GIN 인덱스가 없으면 함께 만든다.

[안전장치] 토큰화는 질의 쪽과 같은 함수(tokenizer.morph_text, MORPH_POS_TAGS)를 쓴다.
다른 필터를 타면 색인 토큰과 질의 토큰이 어긋나 매칭이 조용히 깨진다.
이미 값이 있는 행도 다시 계산해 덮어쓴다.

사용 (호스트에서 실행, DB 기동 전제):
    uv run python scripts/backfill_content_morph.py            # dry-run: 대상 집계·표본만 출력
    uv run python scripts/backfill_content_morph.py --apply    # DB 반영
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

from src.utils.config import CHUNKS_TABLE, MORPH_POS_TAGS  # noqa: E402

# UPDATE 배치 크기 — 1500청크 규모에서 왕복을 줄이되 파라미터 상한에 걸리지 않는 값.
UPDATE_BATCH = 200


def run(apply: bool) -> int:
    """chunks 전 행의 content_morph를 (재)계산한다. apply=False면 집계·표본만 출력한다."""
    # 호스트 실행 시 DB 호스트 보정 (다른 백필·하니스와 동일 규약)
    if os.getenv("POSTGRES_HOST") == "database":
        os.environ["POSTGRES_HOST"] = "localhost"

    from src.db.connection import close_pool, get_pool, init_pool
    from src.retrieval.tokenizer import morph_text

    table = sql.Identifier(CHUNKS_TABLE)
    init_pool()
    try:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                # 집계가 UndefinedColumn으로 죽지 않도록 존재를 먼저 확인한다 — 생성(DDL)은 --apply에서만.
                cur.execute(
                    "SELECT count(*) FROM information_schema.columns "
                    "WHERE table_name = %s AND column_name = 'content_morph'",
                    (CHUNKS_TABLE,),
                )
                has_column = bool(cur.fetchone()[0])
                if has_column:
                    cur.execute(
                        sql.SQL("SELECT count(*), count(content_morph) FROM {t}").format(t=table)
                    )
                    total, filled = cur.fetchone()
                else:
                    cur.execute(sql.SQL("SELECT count(*) FROM {t}").format(t=table))
                    total, filled = cur.fetchone()[0], 0
                print(f"# content_morph backfill {'APPLY' if apply else 'DRY-RUN'}")
                print(f"대상: {CHUNKS_TABLE} {total}청크 · 컬럼 {'있음' if has_column else '없음(apply 시 생성)'} "
                      f"· 이미 채워짐 {filled} — 전 행 재계산·덮어쓰기")
                print(f"품사 화이트리스트: {MORPH_POS_TAGS}")

                cur.execute(
                    sql.SQL("SELECT chunk_id, content FROM {t} ORDER BY chunk_id").format(t=table)
                )
                rows = cur.fetchall()

                # 표본 1건으로 토큰화 결과를 눈으로 확인할 수 있게 한다.
                if rows:
                    cid, content = rows[0]
                    print(f"\n표본 {cid} (원문 앞 60자): {content[:60]}...")
                    print(f"  content_morph: {morph_text(content)[:90]}...")

                if not apply:
                    print("\ndry-run 종료 — 반영하려면 --apply")
                    return 0

                # DDL은 색인 경로와 동일한 멱등 구성 — 컬럼·인덱스가 이미 있으면 아무 일도 하지 않으므로 순서(코드 배포 전/후)에 안전하다.
                cur.execute(
                    sql.SQL("ALTER TABLE {t} ADD COLUMN IF NOT EXISTS content_morph TEXT").format(t=table)
                )
                cur.execute(
                    sql.SQL(
                        "CREATE INDEX IF NOT EXISTS {idx} ON {t} "
                        "USING GIN (to_tsvector('simple', content_morph))"
                    ).format(idx=sql.Identifier(f"{CHUNKS_TABLE}_content_morph_gin_idx"), t=table)
                )

                update_sql = sql.SQL(
                    "UPDATE {t} SET content_morph = %s WHERE chunk_id = %s"
                ).format(t=table)
                t0 = time.perf_counter()
                batch: list[tuple[str, str]] = []
                for i, (chunk_id, content) in enumerate(rows, start=1):
                    batch.append((morph_text(content), chunk_id))
                    if len(batch) >= UPDATE_BATCH or i == len(rows):
                        cur.executemany(update_sql, batch)
                        batch = []
                        print(f"  백필 {i}/{len(rows)} ({time.perf_counter() - t0:.1f}s)")

                cur.execute(
                    sql.SQL("SELECT count(*) - count(content_morph) FROM {t}").format(t=table)
                )
                remaining = cur.fetchone()[0]
                print(f"\n완료 — 미채움 {remaining}건 (0이어야 정상)")
                return 0 if remaining == 0 else 1
    finally:
        close_pool()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="chunks.content_morph 백필 (#261 채택 후속)")
    parser.add_argument("--apply", action="store_true", help="DB에 반영 (기본: dry-run 집계·표본만)")
    return parser


def main(argv: list[str] | None = None) -> int:
    return run(build_parser().parse_args(argv).apply)


if __name__ == "__main__":
    raise SystemExit(main())
