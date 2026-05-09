"""
프로젝트 구조 및 모듈 임포트 무결성 검증

src/ 디렉토리 내 모든 파이썬 파일의 문법 오류를 검사하고,
핵심 모듈들이 의존성 오류 없이 정상적으로 임포트되는지 확인합니다.
"""
import pytest
import importlib
import py_compile
from pathlib import Path

# 검증 대상 모듈 리스트 (의존성 순서 고려)
MODULES_TO_TEST = [
    "src.models.schemas",
    "src.models.state",
    "src.utils.config",
    "src.utils.logger",
    "src.db.vector_store",
    "src.retrieval.searcher",
    "src.retrieval.reranker",
    "src.agent.prompts",
    "src.agent.nodes.rewrite",
    "src.agent.nodes.evaluate",
    "src.agent.nodes.generate",
    "src.agent.workflow"
]


@pytest.mark.unit
class TestProjectStructure:
    """프로젝트 구조 및 모듈 임포트 무결성 검증"""

    def test_syntax_all_files(self):
        """src 디렉토리 내 모든 파이썬 파일의 문법적 오류를 검사합니다."""
        src_path = Path(__file__).parent.parent.parent / "src"
        py_files = list(src_path.glob("**/*.py"))

        for py_file in py_files:
            try:
                py_compile.compile(str(py_file), doraise=True)
            except py_compile.PyCompileError as e:
                pytest.fail(f"Syntax error in {py_file}: {e}")

    @pytest.mark.parametrize("module_name", MODULES_TO_TEST)
    def test_module_imports(self, module_name):
        """정의된 모듈들이 의존성 오류 없이 정상적으로 임포트되는지 검사합니다."""
        try:
            importlib.import_module(module_name)
        except ImportError as e:
            pytest.fail(f"{module_name} 모듈을 불러오는 중 오류 발생: {e}")
        except Exception as e:
            pytest.fail(f"{module_name} 모듈을 불러오는 중 예상치 못한 오류 발생: {e}")

    def test_dependency_chain(self):
        """핵심 워크플로우의 의존성 체인이 올바른지 순차적으로 검증합니다."""
        # 상위 수준 모듈인 workflow가 하위 모듈들을 모두 정상적으로 참조하는지 확인
        try:
            from src.agent import workflow
            assert workflow.build_workflow is not None
            assert workflow.route_after_evaluate is not None
        except Exception as e:
            pytest.fail(f"워크플로우 구동 중 의존성 오류 발생: {e}")
