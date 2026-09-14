import asyncio
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fastapi import HTTPException, UploadFile

import app.main as main
from app.settings import AppSettings
from app.text_chunker import DocumentChunk
from app.vector_store import VectorStore


class RagEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_store = main.vector_store
        self.original_runtime_settings = main.runtime_settings
        main.vector_store = None
        main.runtime_settings = AppSettings(False, "公开演示知识库", 2 * 1024 * 1024, 200, 1000, 32)

    def tearDown(self) -> None:
        main.vector_store = self.original_store
        main.runtime_settings = self.original_runtime_settings

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
            patch("app.main.load_rerank_settings"),
            patch("app.main.embed_texts", return_value=[[0.9, 0.1]]),
            patch("app.main.rerank_results", side_effect=lambda _q, results, _s, _limit: results),
            patch("app.main.answer_from_context", return_value="请联系信息中心报修校园网络。"),
        ):
            result = main.ask_question(main.AskRequest(question="校园网络怎么报修？"))

        self.assertEqual(result["answer"], "请联系信息中心报修校园网络。")
        self.assertEqual(result["sources"][0]["source_file"], "network.txt")
        self.assertEqual(result["sources"][0]["citation_index"], 1)

    def test_rejects_file_larger_than_server_limit(self) -> None:
        main.runtime_settings = AppSettings(False, "公开演示知识库", 3, 200, 1000, 32)
        upload = UploadFile(filename="large.txt", file=BytesIO(b"1234"))

        with self.assertRaisesRegex(HTTPException, "不能超过"):
            asyncio.run(main.preview_document(upload))

    def test_rejects_blank_document_with_chinese_error(self) -> None:
        upload = UploadFile(filename="blank.txt", file=BytesIO("   ".encode("utf-8")))

        with self.assertRaisesRegex(HTTPException, "待切分文本不能为空"):
            asyncio.run(main.split_uploaded_document(upload))

    def test_rejects_document_with_too_many_chunks(self) -> None:
        main.runtime_settings = AppSettings(False, "公开演示知识库", 2 * 1024 * 1024, 1, 1000, 32)
        upload = UploadFile(filename="long.txt", file=BytesIO(("a" * 801).encode("utf-8")))

        with self.assertRaisesRegex(HTTPException, "不能超过 1 个段落"):
            asyncio.run(main.split_uploaded_document(upload))

    def test_rejects_question_larger_than_server_limit(self) -> None:
        main.runtime_settings = AppSettings(False, "公开演示知识库", 2 * 1024 * 1024, 200, 3, 32)

        with self.assertRaisesRegex(HTTPException, "问题不能超过 3 个字符"):
            main.search_documents("超过限制")

    def test_public_demo_rejects_all_write_actions(self) -> None:
        main.runtime_settings = AppSettings(True, "公开演示知识库", 2 * 1024 * 1024, 200, 1000, 32)
        upload = UploadFile(filename="guide.txt", file=BytesIO("公开资料".encode("utf-8")))

        with self.assertRaisesRegex(HTTPException, "只读模式"):
            main.create_knowledge_base(main.KnowledgeBaseCreateRequest(name="新知识库"))
        with self.assertRaisesRegex(HTTPException, "只读模式"):
            asyncio.run(main.preview_document(upload))
        with self.assertRaisesRegex(HTTPException, "只读模式"):
            asyncio.run(
                main.split_uploaded_document(
                    UploadFile(filename="guide.txt", file=BytesIO("公开资料".encode("utf-8")))
                )
            )
        with self.assertRaisesRegex(HTTPException, "只读模式"):
            asyncio.run(
                main.index_uploaded_document(
                    UploadFile(filename="guide.txt", file=BytesIO("公开资料".encode("utf-8")))
                )
            )
        with self.assertRaisesRegex(HTTPException, "只读模式"):
            main.select_knowledge_base(1)
        with self.assertRaisesRegex(HTTPException, "只读模式"):
            main.clear_knowledge_base()
