import asyncio
from io import BytesIO
import unittest
from unittest.mock import patch

from fastapi import UploadFile

import app.main as main


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
        ):
            index_result = asyncio.run(main.index_uploaded_document(upload))
            search_result = main.search_documents("网络无法连接", limit=1)

        self.assertEqual(index_result["chunk_count"], 1)
        self.assertEqual(index_result["indexed_chunk_count"], 1)
        self.assertEqual(search_result["results"][0]["source_file"], "network.txt")
        self.assertEqual(search_result["results"][0]["chunk_index"], 0)

    def test_rejects_search_before_any_document_is_indexed(self) -> None:
        with self.assertRaisesRegex(Exception, "尚未建立知识库索引"):
            main.search_documents("网络无法连接")
