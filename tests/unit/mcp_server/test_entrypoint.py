"""패키지 진입점 등록 검증 (#264)."""

import tomllib
from pathlib import Path


def test_mcp_server_exposes_main_callable():
    from src.mcp_server import server

    assert callable(server.main)


def test_pyproject_registers_mcp_console_script():
    root = Path(__file__).resolve().parents[3]
    data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    assert data["project"]["scripts"]["rag-accounting-mcp"] == "src.mcp_server.server:main"


def test_pyproject_declares_hatchling_build_system_with_src_package():
    root = Path(__file__).resolve().parents[3]
    data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    assert data["build-system"]["build-backend"] == "hatchling.build"
    assert data["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"] == ["src"]
