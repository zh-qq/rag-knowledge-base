from dataclasses import dataclass

import faiss
import numpy as np

from app.text_chunker import DocumentChunk


class VectorStoreError(ValueError):
    """向量与索引规则不匹配时抛出。"""


@dataclass(frozen=True)
class SearchResult:
    source_file: str
    chunk_index: int
    content: str
    score: float


class VectorStore:
    """使用余弦相似度的内存向量索引。"""

    def __init__(self, dimension: int) -> None:
        if dimension <= 0:
            raise VectorStoreError("向量维度必须大于 0")

        self.dimension = dimension
        self.index = faiss.IndexFlatIP(dimension)
        self.chunks: list[DocumentChunk] = []

    def add(self, chunks: list[DocumentChunk], vectors: list[list[float]]) -> None:
        if not chunks:
            raise VectorStoreError("待索引段落不能为空")
        if len(chunks) != len(vectors):
            raise VectorStoreError("段落数量与向量数量必须一致")

        matrix = self._to_matrix(vectors)
        faiss.normalize_L2(matrix)
        self.index.add(matrix)
        self.chunks.extend(chunks)

    def search(self, query_vector: list[float], limit: int = 3) -> list[SearchResult]:
        if limit <= 0:
            raise VectorStoreError("返回数量必须大于 0")
        if not self.chunks:
            return []

        query = self._to_matrix([query_vector])
        faiss.normalize_L2(query)
        scores, indexes = self.index.search(query, min(limit, len(self.chunks)))

        return [
            SearchResult(
                source_file=self.chunks[index].source_file,
                chunk_index=self.chunks[index].chunk_index,
                content=self.chunks[index].content,
                score=float(score),
            )
            for score, index in zip(scores[0], indexes[0])
            if index >= 0
        ]

    def _to_matrix(self, vectors: list[list[float]]) -> np.ndarray:
        matrix = np.asarray(vectors, dtype=np.float32)
        if matrix.ndim != 2 or matrix.shape[1] != self.dimension:
            raise VectorStoreError(f"向量维度必须为 {self.dimension}")
        if not np.isfinite(matrix).all():
            raise VectorStoreError("向量不能包含无效数值")
        return matrix
