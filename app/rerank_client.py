"""百炼文本重排序客户端。"""

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.settings import RerankSettings
from app.vector_store import SearchResult


class RerankError(RuntimeError):
    """云端重排序服务调用失败时抛出。"""


def rerank_results(
    question: str,
    candidates: list[SearchResult],
    settings: RerankSettings,
    limit: int = 3,
) -> list[SearchResult]:
    """将 FAISS 候选按问答相关性重排序，保留原始来源信息。"""
    if not question.strip():
        raise RerankError("问题不能为空")
    if not candidates:
        raise RerankError("没有可重排序的候选资料")
    if limit <= 0 or limit > len(candidates):
        raise RerankError("重排序返回数量不合法")

    payload = {
        "model": settings.model,
        "query": question,
        "documents": [candidate.content for candidate in candidates],
        "top_n": limit,
        "instruct": "Given a web search query, retrieve relevant passages that answer the query.",
    }
    request = Request(
        f"{settings.base_url}/reranks",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {settings.api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=20) as response:
            response_data = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        raise RerankError("云端重排序服务请求失败") from error
    except URLError as error:
        raise RerankError("无法连接云端重排序服务") from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RerankError("云端重排序服务返回异常") from error

    results = response_data.get("results")
    if not isinstance(results, list):
        raise RerankError("云端重排序服务返回格式异常")

    reranked: list[SearchResult] = []
    seen_indexes: set[int] = set()
    try:
        for item in results[:limit]:
            index = int(item["index"])
            score = float(item["relevance_score"])
            if index < 0 or index >= len(candidates) or index in seen_indexes:
                raise ValueError
            seen_indexes.add(index)
            candidate = candidates[index]
            reranked.append(
                SearchResult(
                    source_file=candidate.source_file,
                    chunk_index=candidate.chunk_index,
                    content=candidate.content,
                    score=score,
                )
            )
    except (KeyError, TypeError, ValueError) as error:
        raise RerankError("云端重排序服务返回结果异常") from error

    if len(reranked) != min(limit, len(candidates)):
        raise RerankError("云端重排序服务未返回足够结果")
    return reranked
