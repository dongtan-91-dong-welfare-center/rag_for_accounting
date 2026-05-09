import pytest

# 단위 테스트 전용 환경 및 Mock 설정
# DB 연결, 외부 API(OpenAI 등) 호출 없이 빠르고 독립적으로 실행되도록 구성

@pytest.fixture(autouse=True)
def mock_external_dependencies(monkeypatch):
    """
    단위 테스트 실행 시 실수로 외부 의존성을 호출하는 것을 방지하기 위해 
    환경 변수를 가짜 값으로 설정
    """
    monkeypatch.setenv("OPENAI_API_KEY", "mock-openai-key-for-unit-test")
    monkeypatch.setenv("POSTGRES_USER", "mock_user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "mock_pass")
    monkeypatch.setenv("POSTGRES_DB", "mock_db")
    monkeypatch.setenv("POSTGRES_HOST", "localhost")
