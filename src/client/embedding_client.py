import httpx

from src.utils import config


def _post(path: str, payload: dict) -> httpx.Response:
    response = httpx.post(
        f"{config.EMBEDDING_SERVER_URL}{path}",
        json=payload,
        timeout=config.EMBEDDING_SERVER_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response


def embed_texts(texts: list[str]) -> list[list[float]]:
    """TEI /embed 호출. normalize=true로 로컬 경로와 pgvector 코사인 정합 동일."""
    payload = {"inputs": texts, "normalize": True, "truncate": False}
    return _post("/embed", payload).json()


def count_tokens(text: str) -> int:
    """TEI /tokenize 호출. 로컬 경로와 같은 토크나이저라 IX-201 판정 기준 동일."""
    tokens_per_input = _post("/tokenize", {"inputs": [text]}).json()
    return len(tokens_per_input[0])
