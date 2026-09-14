from openai import APIError, OpenAI

from app.settings import ChatSettings
from app.vector_store import SearchResult


class ChatError(RuntimeError):
    """云端对话模型调用失败时抛出。"""


def answer_from_context(
    question: str,
    results: list[SearchResult],
    settings: ChatSettings,
) -> str:
    """只根据检索到的文本段落生成回答。"""
    if not question.strip():
        raise ChatError("问题不能为空")
    if not results:
        raise ChatError("没有可用于回答的资料")

    context = "\n\n".join(
        f"【来源：{result.source_file}，段落 {result.chunk_index}】\n{result.content}"
        for result in results
    )
    messages = [
        {
            "role": "system",
            "content": "你是知识库问答助手。只能依据提供的资料回答；资料不足时直接说明资料未提供答案。请用简洁中文回答。",
        },
        {
            "role": "user",
            "content": f"资料：\n{context}\n\n问题：{question}",
        },
    ]

    try:
        client = OpenAI(api_key=settings.api_key, base_url=settings.base_url)
        response = client.chat.completions.create(
            model=settings.model,
            messages=messages,
            temperature=0.2,
        )
    except APIError as error:
        raise ChatError("云端对话模型调用失败") from error

    answer = response.choices[0].message.content
    if not answer:
        raise ChatError("云端对话模型未返回回答")
    return answer
