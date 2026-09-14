import asyncio
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fastapi import UploadFile

import app.main as main
from app.text_chunker import DocumentChunk
from app.vector_store import VectorStore


class RagEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_store = main.vector_store
        main.vector_store = None

    def tearDown(self) -> None:
        main.vector_store = self.original_store

    def test_indexes_document_then_returns_matching_search_result(self) -> None:
        upload = UploadFile(
            filename="network.txt",
            file=BytesIO("校园网络报修请联系信息中心。".encode("utf-8")),
        )

        with (
            patch("app.main.load_embedding_settings"),
            patch("app.main.embed_texts", side_effect=[[[1.0, 0.0]], [[0.9, 0.1]]]),
            patch("app.main.save_vector_store"),
        ):
            index_result = asyncio.run(main.index_uploaded_document(upload))
            search_result = main.search_documents("网络无法连接", limit=1)

        self.assertEqual(index_result["chunk_count"], 1)
        self.assertEqual(index_result["indexed_chunk_count"], 1)
        self.assertEqual(search_result["results"][0]["source_file"], "network.txt")
        self.assertEqual(search_result["results"][0]["chunk_index"], 0)

    def test_returns_current_knowledge_base_status(self) -> None:
        main.vector_store = VectorStore(dimension=2)
        main.vector_store.add([DocumentChunk("network.txt", 0, "校园网络报修流程")], [[1.0, 0.0]])

        result = main.knowledge_base_status()

        self.assertEqual(result["indexed_chunk_count"], 1)

    def test_clears_saved_knowledge_base(self) -> None:
        store = VectorStore(dimension=2)
        store.add([DocumentChunk("network.txt", 0, "校园网络报修流程")], [[1.0, 0.0]])

        with TemporaryDirectory() as directory:
            index_path = Path(directory) / "knowledge_base.faiss"
            metadata_path = Path(directory) / "chunks.json"
            store.save(index_path, metadata_path)
            main.vector_store = store

            with (
                patch("app.main.INDEX_PATH", index_path),
                patch("app.main.METADATA_PATH", metadata_path),
            ):
                result = main.clear_knowledge_base()

            self.assertFalse(index_path.exists())
            self.assertFalse(metadata_path.exists())

        self.assertEqual(result["indexed_chunk_count"], 0)
        self.assertIsNone(main.vector_store)

    def test_rejects_search_before_any_document_is_indexed(self) -> None:
        with self.assertRaisesRegex(Exception, "尚未建立知识库索引"):
            main.search_documents("网络无法连接")

    def test_returns_answer_with_sources(self) -> None:
        main.vector_store = VectorStore(dimension=2)
        main.vector_store.add(
            [DocumentChunk("network.txt", 0, "校园网络报修请联系信息中心。")],
            [[1.0, 0.0]],
        )

        with (
            patch("app.main.load_embedding_settings"),
            patch("app.main.load_chat_settings"),
            patch("app.main.embed_texts", return_value=[[0.9, 0.1]]),
            patch("app.main.answer_from_context", return_value="请联系信息中心报修校园网络。"),
        ):
            result = main.ask_question(main.AskRequest(question="校园网络怎么报修？"))

        self.assertEqual(result["answer"], "请联系信息中心报修校园网络。")
        self.assertEqual(result["sources"][0]["source_file"], "network.txt")
