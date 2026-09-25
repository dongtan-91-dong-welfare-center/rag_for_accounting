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
    """
    TEI /embed 호출. normalize=true로 로컬 경로와 pgvector 코사인 정합 동일.

    config.EMBEDDING_ENCODE_BATCH_SIZE 단위로 미니배치를 분할 전송하여
    TEI_MAX_CLIENT_BATCH_SIZE 초과로 인한 HTTP 422 오류를 방지합니다.
    """
    if not texts:
        return []

    batch_size = max(1, config.EMBEDDING_ENCODE_BATCH_SIZE)
    results: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        payload = {"inputs": batch, "normalize": True, "truncate": False}
        batch_embeddings = _post("/embed", payload).json()
        results.extend(batch_embeddings)
    return results


def count_tokens(text: str) -> int:
    """TEI /tokenize 호출. 로컬 경로와 같은 토크나이저라 IX-201 판정 기준 동일."""
    tokens_per_input = _post("/tokenize", {"inputs": [text]}).json()
    return len(tokens_per_input[0])
