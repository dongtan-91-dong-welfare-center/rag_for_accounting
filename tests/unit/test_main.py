"""
src/main.py 질의 진입점 단위 테스트

검증 범위:
    - run_query(): run_workflow 전에 임베딩 preload를 호출해 콜드 로드를 step_timeout(노드 30s) 밖으로 분리한다.
      preload가 실패해도 워크플로는 진행한다.

run_workflow/init_pool 등 외부 의존은 mock으로 차단해 라이브 모델·DB 없이 진입점 논리만 검증한다.
"""
import argparse
from pathlib import Path
from unittest.mock import patch

import pytest

from src.utils.exception import LLMAPIConnectionError


def _args(query="질문", standard="ALL"):
    return argparse.Namespace(query=query, standard=standard)


@pytest.mark.unit
class TestRunQueryPreload:
    """run_query() — 첫 질의 콜드 로드 preload 회귀 가드"""

    def test_preloads_before_workflow(self):
        """run_workflow 호출 전에 임베딩·리랭커를 preload한다(임베딩 → 리랭커 → 워크플로 순)."""
        from src import main

        order = []
        with patch.object(main, "init_pool"), \
             patch.object(main, "close_pool"), \
             patch.object(main, "_print_response"), \
             patch("src.clients.embedding.warmup_model", side_effect=lambda: order.append("warmup")), \
             patch("src.retrieval.reranker.warmup_reranker", side_effect=lambda: order.append("rerank")), \
             patch("src.agent.workflow.run_workflow",
                   side_effect=lambda q, standard_filter="ALL": order.append("workflow") or {"thread_id": "t"}):
            rc = main.run_query(_args())

        assert rc == 0
        assert order == ["warmup", "rerank", "workflow"]    # 두 preload가 워크플로보다 먼저

    def test_preload_failure_does_not_block(self):
        """preload 실패(HF 접속 불가 등)해도 워크플로는 진행된다(lazy 폴백)."""
        from src import main

        ran = []
        with patch.object(main, "init_pool"), \
             patch.object(main, "close_pool"), \
             patch.object(main, "_print_response"), \
             patch("src.clients.embedding.warmup_model",
                   side_effect=LLMAPIConnectionError("HF 차단", node="search")), \
             patch("src.retrieval.reranker.warmup_reranker"), \
             patch("src.agent.workflow.run_workflow",
                   side_effect=lambda q, standard_filter="ALL": ran.append("workflow") or {"thread_id": "t"}):
            rc = main.run_query(_args())

        assert rc == 0
        assert ran == ["workflow"]    # preload 실패에도 워크플로는 실행됨


@pytest.mark.unit
class TestRunMigrate:
    """run_migrate() — CLI migrate 서브커맨드 검증"""

    def test_run_migrate_success(self):
        from src import main
        from src.db.migrator import Migration

        mock_migration = Migration(version="0001", name="0001_initial.sql", path=Path("dummy"))
        with patch("src.db.migrator.run_migrations", return_value=[mock_migration]), \
             patch.object(main, "close_pool"):
            rc = main.run_migrate(argparse.Namespace())

        assert rc == 0

    def test_run_migrate_failure(self):
        from src import main

        with patch("src.db.migrator.run_migrations", side_effect=RuntimeError("DB 접속 에러")), \
             patch.object(main, "close_pool"):
            rc = main.run_migrate(argparse.Namespace())

        assert rc == 1


@pytest.mark.unit
class TestInputLengthLimit:
    """CLI 입력 길이 상한(#445)"""

    def test_over_length_query_is_rejected_before_pool_init(self, capsys):
        """상한 초과 질의는 DB 풀 초기화 전에 오류 코드 1로 거절한다."""
        from src import main
        from src.utils.config import MAX_QUERY_LENGTH

        with patch.object(main, "init_pool") as init_pool:
            rc = main.run_query(_args(query="가" * (MAX_QUERY_LENGTH + 1)))

        assert rc == 1
        init_pool.assert_not_called()
        assert "이내로 입력" in capsys.readouterr().err

    def test_over_length_feedback_is_reprompted(self, capsys):
        """상한 초과 재작성 피드백은 안내 후 다시 입력받는다."""
        from src import main
        from src.utils.config import MAX_FEEDBACK_LENGTH

        answers = iter(["r", "가" * (MAX_FEEDBACK_LENGTH + 1), "리스 강조"])
        with patch.object(main.sys.stdin, "isatty", return_value=True),              patch("builtins.input", side_effect=lambda _="": next(answers)):
            decision = main._prompt_human_decision({})

        assert decision == {"action": "rewrite", "feedback": "리스 강조"}
        assert "이내로 입력" in capsys.readouterr().out
