"""src/main.py ingest 워커 재기동(--docs-per-restart) 단위 테스트 (#150).

자식 프로세스는 subprocess.run을 대체해 실제 모델·DB 없이 부모의 분할·집계·실패 처리 논리만 검증한다.
"""
import argparse
import json
import subprocess
from pathlib import Path

import pytest
from unittest.mock import patch

from src import main

pytestmark = pytest.mark.unit


def _ns(tmp_path, **kw):
    base = dict(
        ontology_dir=str(tmp_path), ontology_files=None, summary_file=None, pdf=None, md=None,
        standard_id=None, standard_type=None, collection="chunks", reset=False,
        clause_level=False, max_tokens=2048, docs_per_restart=2,
    )
    base.update(kw)
    return argparse.Namespace(**base)


def _make_jsons(tmp_path, n):
    for i in range(n):
        (tmp_path / f"d{i}.json").write_text("{}", encoding="utf-8")


def _fake_child(calls, fail_batch=None, chunks_per_doc=3):
    """자식 실행을 흉내 낸다: 요약 파일을 쓰고 종료 코드를 돌려준다."""

    def run(cmd, check=False):
        calls.append(cmd)
        summary = Path(cmd[cmd.index("--summary-file") + 1])
        idx = len(calls) - 1
        if fail_batch is not None and idx == fail_batch:
            return subprocess.CompletedProcess(cmd, 1)
        summary.write_text(
            json.dumps([{"document_id": Path(f).stem, "chunk_count": chunks_per_doc, "status": "success"}
                        for f in cmd[cmd.index("--ontology-files") + 1 : cmd.index("--summary-file")]]),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(cmd, 0)

    return run


def test_split_into_batches():
    assert main._split_batches(list("abcde"), 2) == [["a", "b"], ["c", "d"], ["e"]]
    assert main._split_batches(list("ab"), 5) == [["a", "b"]]


def test_parser_exposes_option_with_off_default():
    a = main.build_parser().parse_args(["ingest"])
    assert a.docs_per_restart == 0
    assert main.build_parser().parse_args(["ingest", "--docs-per-restart", "3"]).docs_per_restart == 3


def test_spawns_one_child_per_batch_without_reset(tmp_path, capsys):
    _make_jsons(tmp_path, 5)
    calls = []
    with patch.object(main.subprocess, "run", side_effect=_fake_child(calls)):
        rc = main._run_ingest_with_restarts(_ns(tmp_path))
    assert rc == 0
    assert len(calls) == 3  # 5개 문서를 2개씩
    assert all("--reset" not in c and "--docs-per-restart" not in c for c in calls)
    assert "총 15청크" in capsys.readouterr().out


def test_reset_runs_once_in_parent_not_children(tmp_path):
    _make_jsons(tmp_path, 3)
    calls = []
    with patch.object(main.subprocess, "run", side_effect=_fake_child(calls)), \
         patch.object(main, "init_pool"), patch.object(main, "close_pool"), \
         patch("src.db.vector_store.delete_collection") as dc:
        main._run_ingest_with_restarts(_ns(tmp_path, reset=True))
    dc.assert_called_once_with("chunks")
    assert all("--reset" not in c for c in calls)


def test_failed_batch_continues_and_returns_1(tmp_path, capsys):
    _make_jsons(tmp_path, 4)
    calls = []
    with patch.object(main.subprocess, "run", side_effect=_fake_child(calls, fail_batch=0)):
        rc = main._run_ingest_with_restarts(_ns(tmp_path))
    out = capsys.readouterr().out
    assert rc == 1
    assert len(calls) == 2  # 첫 배치가 실패해도 다음 배치를 계속 진행한다
    assert "실패" in out and "d0.json" in out


def test_options_are_forwarded_to_children(tmp_path):
    _make_jsons(tmp_path, 1)
    calls = []
    with patch.object(main.subprocess, "run", side_effect=_fake_child(calls)):
        main._run_ingest_with_restarts(_ns(tmp_path, clause_level=True, max_tokens=1024, collection="c2"))
    cmd = calls[0]
    assert "--clause-level" in cmd
    assert cmd[cmd.index("--max-tokens") + 1] == "1024"
    assert cmd[cmd.index("--collection") + 1] == "c2"


def test_restart_not_allowed_with_single_source(tmp_path, capsys):
    rc = main.run_ingest(_ns(tmp_path, md="a.md", standard_id="x", standard_type="GAAP"))
    assert rc == 1


def test_empty_dir_returns_1(tmp_path):
    assert main._run_ingest_with_restarts(_ns(tmp_path)) == 1


def test_child_mode_uses_explicit_files_and_writes_summary(tmp_path):
    f = tmp_path / "a.json"
    f.write_text("{}", encoding="utf-8")
    summary = tmp_path / "s.json"
    args = _ns(tmp_path, docs_per_restart=0, ontology_files=[str(f)], summary_file=str(summary))
    with patch.object(main, "init_pool"), patch.object(main, "close_pool"), \
         patch.object(main, "_load_graph_from_json", return_value=object()), \
         patch.object(main, "_index_graph",
                      return_value={"document_id": "a", "chunk_count": 2, "status": "success"}):
        rc = main.run_ingest(args)
    assert rc == 0
    assert json.loads(summary.read_text(encoding="utf-8"))[0]["chunk_count"] == 2
