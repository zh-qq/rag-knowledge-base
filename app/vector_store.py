from dataclasses import dataclass
import json
from pathlib import Path

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

    @property
    def count(self) -> int:
        return len(self.chunks)

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

    def save(self, index_path: Path, metadata_path: Path) -> None:
        """将 FAISS 索引和段落信息保存到本地文件。"""
        index_temp_path = index_path.with_suffix(index_path.suffix + ".tmp")
        metadata_temp_path = metadata_path.with_suffix(metadata_path.suffix + ".tmp")

        try:
            index_path.parent.mkdir(parents=True, exist_ok=True)
            metadata_path.parent.mkdir(parents=True, exist_ok=True)
            faiss.write_index(self.index, str(index_temp_path))
            metadata = [
                {
                    "source_file": chunk.source_file,
                    "chunk_index": chunk.chunk_index,
                    "content": chunk.content,
                }
                for chunk in self.chunks
            ]
            metadata_temp_path.write_text(
                json.dumps(metadata, ensure_ascii=False), encoding="utf-8"
            )
            index_temp_path.replace(index_path)
            metadata_temp_path.replace(metadata_path)
        except (OSError, TypeError, ValueError) as error:
            raise VectorStoreError("保存知识库索引失败") from error

    @classmethod
    def load(cls, index_path: Path, metadata_path: Path) -> "VectorStore | None":
        """从本地文件恢复 FAISS 索引和段落信息。"""
        if not index_path.exists() and not metadata_path.exists():
            return None
        if not index_path.exists() or not metadata_path.exists():
            raise VectorStoreError("知识库索引文件不完整")

        try:
            index = faiss.read_index(str(index_path))
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            chunks = [
                DocumentChunk(
                    source_file=item["source_file"],
                    chunk_index=item["chunk_index"],
                    content=item["content"],
                )
                for item in metadata
            ]
        except (OSError, TypeError, ValueError, KeyError, json.JSONDecodeError) as error:
            raise VectorStoreError("读取知识库索引失败") from error

        if index.ntotal != len(chunks):
            raise VectorStoreError("知识库索引与段落信息数量不一致")

        store = cls(dimension=index.d)
        store.index = index
        store.chunks = chunks
        return store

    def _to_matrix(self, vectors: list[list[float]]) -> np.ndarray:
        matrix = np.asarray(vectors, dtype=np.float32)
        if matrix.ndim != 2 or matrix.shape[1] != self.dimension:
            raise VectorStoreError(f"向量维度必须为 {self.dimension}")
        if not np.isfinite(matrix).all():
            raise VectorStoreError("向量不能包含无效数值")
        return matrix
