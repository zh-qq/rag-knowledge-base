from openai import APIError, OpenAI

from app.settings import EmbeddingSettings


class EmbeddingError(RuntimeError):
    """云端向量服务调用失败时抛出。"""


def embed_texts(texts: list[str], settings: EmbeddingSettings) -> list[list[float]]:
    """调用兼容 OpenAI 协议的云端接口，为文本生成向量。"""
    if not texts:
        raise EmbeddingError("待向量化文本不能为空")

    try:
        client = OpenAI(api_key=settings.api_key, base_url=settings.base_url)
        response = client.embeddings.create(model=settings.model, input=texts)
    except APIError as error:
        raise EmbeddingError("云端向量服务调用失败") from error

    return [item.embedding for item in response.data]
