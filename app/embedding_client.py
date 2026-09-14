from openai import APIError, OpenAI

from app.settings import EmbeddingSettings


class EmbeddingError(RuntimeError):
    """云端向量服务调用失败时抛出。"""


def embed_texts(
    texts: list[str], settings: EmbeddingSettings, batch_size: int = 32
) -> list[list[float]]:
    """调用兼容 OpenAI 协议的云端接口，为文本生成向量。"""
    if not texts:
        raise EmbeddingError("待向量化文本不能为空")
    if batch_size <= 0:
        raise EmbeddingError("向量批次大小必须大于 0")

    try:
        client = OpenAI(api_key=settings.api_key, base_url=settings.base_url)
        vectors: list[list[float]] = []
        for start in range(0, len(texts), batch_size):
            response = client.embeddings.create(
                model=settings.model,
                input=texts[start : start + batch_size],
            )
            vectors.extend(item.embedding for item in response.data)
    except APIError as error:
        raise EmbeddingError("云端向量服务调用失败") from error

    if len(vectors) != len(texts):
        raise EmbeddingError("云端向量服务返回数量异常")
    return vectors
