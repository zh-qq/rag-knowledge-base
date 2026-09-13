from dataclasses import dataclass
from typing import Final


DEFAULT_CHUNK_SIZE: Final = 800
DEFAULT_CHUNK_OVERLAP: Final = 100


class TextChunkError(ValueError):
    """文本无法按当前规则切分时抛出。"""


@dataclass(frozen=True)
class DocumentChunk:
    source_file: str
    chunk_index: int
    content: str


def split_document(
    source_file: str,
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[DocumentChunk]:
    """按字符数切分文档，并保留来源文件与段落序号。"""
    if not text.strip():
        raise TextChunkError("待切分文本不能为空")
    if chunk_size <= 0:
        raise TextChunkError("每段字符数必须大于 0")
    if overlap < 0 or overlap >= chunk_size:
        raise TextChunkError("重叠字符数必须大于等于 0 且小于每段字符数")

    chunks: list[DocumentChunk] = []
    start = 0
    chunk_index = 0

    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(
            DocumentChunk(
                source_file=source_file,
                chunk_index=chunk_index,
                content=text[start:end],
            )
        )
        if end == len(text):
            break
        start = end - overlap
        chunk_index += 1

    return chunks
