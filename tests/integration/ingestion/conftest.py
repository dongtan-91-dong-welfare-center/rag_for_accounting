"""ingestion 통합 테스트# 전용 픽스처.

이 디렉터리의 테스트는 외부 의존(파싱·임베딩·DB)만 모킹하고 실제 청킹(chunk_graph)·인덱싱(index_documents) 모듈을 그대로 관통한다.
따라서 라이브 인프라(Docker/모델 다운로드)없이 통과해야 한다.

상위 `tests/integration/conftest.py`의 세션 게이트(`check_integration_env`)는
OPENAI_API_KEY·Docker 인프라가 없으면 통합 테스트 전체를 skip시키는데, 
트랙 B는 그런 의존이 없으므로 동명 픽스처로 오버라이드하여 게이트를 무력화한다.
pytest는 테스트와 더 가까운 conftest에 정의된 동명 픽스처를 우선 사용한다.
"""
from unittest.mock import MagicMock, patch

import pytest

from src.utils.config import EMBEDDING_DIM


@pytest.fixture(scope="session", autouse=True)
def check_integration_env():
    """상위 conftest의 인프라/환경 게이트를 무력화하는 동명 오버라이드.

    트랙 B는 외부 의존을 전부 모킹하므로 OPENAI_API_KEY·Docker 점검을 건너뛰고
    라이브 인프라 없이 통과해야 한다.
    """
    yield


@pytest.fixture
def mock_db_pool():
    """psycopg3 커넥션 풀과 커서를 mock한다.

    `tests/unit/db/test_vector_store.py`의 동명 픽스처를 ingestion conftest로 승격해 재사용한다.
    """
    with patch("src.db.vector_store.get_pool") as mock_get_pool:
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_cur = MagicMock()

        mock_get_pool.return_value = mock_pool
        mock_pool.connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur

        yield mock_cur


@pytest.fixture
def mock_embedding():
    """KURE-v1 임베딩(embed_texts)·토큰 계산(count_tokens)을 mock한다.

    `tests/unit/db/test_vector_store.py`의 동명 픽스처를 ingestion conftest로 승격해 재사용한다.
    """
    with patch("src.db.vector_store.embed_texts") as mock_embed, \
         patch("src.db.vector_store.count_tokens") as mock_count:
        mock_embed.side_effect = lambda texts, node="index": [[0.1] * EMBEDDING_DIM for _ in texts] # 0.1이 EMBEDDING_DIM(1536)개 들어있는 플로팅 넘버 리스트(벡터)를 만들기 위해
        mock_count.return_value = 10    # 기본: 토큰 한도 이내
        yield mock_embed, mock_count


@pytest.fixture(autouse=True)
def _close_pool_teardown():
    """각 테스트 종료 시 전역 커넥션 풀을 명시적으로 닫아 `_pool` 누출을 방지한다.

    get_pool은 mock으로 차단되어 실제 풀이 열리지 않는 것이 정상이지만, 어떤 경로로든
    init_pool이 호출된 경우를 대비해 teardown에서 close_pool()을 안전하게 호출한다.
    """
    yield
    from src.db.connection import close_pool

    close_pool()
