"""Supabase 中知识库数据的最小读写封装。"""

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.settings import SupabaseSettings
from app.text_chunker import DocumentChunk
from app.vector_store import VectorStore, VectorStoreError


class KnowledgeBaseRepositoryError(RuntimeError):
    """云端知识库存储不可用或返回数据异常时抛出。"""


@dataclass(frozen=True)
class KnowledgeBase:
    id: int
    name: str


class SupabaseKnowledgeBaseRepository:
    """通过 Supabase REST API 保存知识库，不向浏览器暴露服务端密钥。"""

    def __init__(self, settings: SupabaseSettings) -> None:
        self._base_url = settings.url.rstrip("/") + "/rest/v1"
        self._api_key = settings.secret_key

    def list_knowledge_bases(self) -> list[KnowledgeBase]:
        rows = self._request("GET", "knowledge_bases", {"select": "id,name", "order": "id.asc"})
        return [KnowledgeBase(id=int(row["id"]), name=str(row["name"])) for row in rows]

    def create_knowledge_base(self, name: str) -> KnowledgeBase:
        rows = self._request(
            "POST",
            "knowledge_bases",
            body={"name": name},
            prefer="return=representation",
        )
        if not rows:
            raise KnowledgeBaseRepositoryError("创建知识库失败")
        return KnowledgeBase(id=int(rows[0]["id"]), name=str(rows[0]["name"]))

    def save_document(
        self,
        knowledge_base_id: int,
        source_file: str,
        chunks: list[DocumentChunk],
        vectors: list[list[float]],
    ) -> None:
        if len(chunks) != len(vectors):
            raise KnowledgeBaseRepositoryError("段落数量与向量数量不一致")

        document_rows = self._request(
            "POST",
            "documents",
            body={"knowledge_base_id": knowledge_base_id, "source_file": source_file},
            prefer="return=representation",
        )
        if not document_rows:
            raise KnowledgeBaseRepositoryError("保存文档失败")

        document_id = int(document_rows[0]["id"])
        chunk_rows = [
            {
                "document_id": document_id,
                "chunk_index": chunk.chunk_index,
                "content": chunk.content,
                "embedding": vector,
            }
            for chunk, vector in zip(chunks, vectors)
        ]
        try:
            self._request("POST", "document_chunks", body=chunk_rows)
        except KnowledgeBaseRepositoryError:
            self._request("DELETE", "documents", {"id": f"eq.{document_id}"})
            raise

    def load_vector_store(self, knowledge_base_id: int) -> VectorStore | None:
        rows = self._request(
            "GET",
            "documents",
            {
                "knowledge_base_id": f"eq.{knowledge_base_id}",
                "select": "source_file,document_chunks(chunk_index,content,embedding)",
                "order": "id.asc",
            },
        )
        chunks: list[DocumentChunk] = []
        vectors: list[list[float]] = []
        for document in rows:
            for chunk in document.get("document_chunks", []):
                chunks.append(
                    DocumentChunk(
                        source_file=str(document["source_file"]),
                        chunk_index=int(chunk["chunk_index"]),
                        content=str(chunk["content"]),
                    )
                )
                vectors.append(list(chunk["embedding"]))

        if not chunks:
            return None
        try:
            store = VectorStore(dimension=len(vectors[0]))
            store.add(chunks, vectors)
            return store
        except (TypeError, VectorStoreError) as error:
            raise KnowledgeBaseRepositoryError("云端知识库向量数据异常") from error

    def clear_knowledge_base(self, knowledge_base_id: int) -> None:
        self._request("DELETE", "documents", {"knowledge_base_id": f"eq.{knowledge_base_id}"})

    def _request(
        self,
        method: str,
        table: str,
        query: dict[str, str] | None = None,
        body: dict[str, Any] | list[dict[str, Any]] | None = None,
        prefer: str | None = None,
    ) -> list[dict[str, Any]]:
        url = f"{self._base_url}/{table}"
        if query:
            url += "?" + urlencode(query)
        headers = {
            "apikey": self._api_key,
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        if prefer:
            headers["Prefer"] = prefer
        data = json.dumps(body).encode("utf-8") if body is not None else None

        try:
            with urlopen(Request(url, data=data, headers=headers, method=method), timeout=20) as response:
                raw_response = response.read().decode("utf-8")
        except HTTPError as error:
            raise KnowledgeBaseRepositoryError("云端知识库存储请求失败") from error
        except URLError as error:
            raise KnowledgeBaseRepositoryError("无法连接云端知识库存储") from error

        if not raw_response:
            return []
        try:
            return json.loads(raw_response)
        except json.JSONDecodeError as error:
            raise KnowledgeBaseRepositoryError("云端知识库存储返回异常") from error
