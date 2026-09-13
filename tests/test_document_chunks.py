import asyncio
from io import BytesIO
import unittest

from fastapi import UploadFile

from app.main import split_uploaded_document


class DocumentChunkEndpointTests(unittest.TestCase):
    def test_returns_chunks_for_uploaded_file(self) -> None:
        upload = UploadFile(filename="notice.txt", file=BytesIO("校园通知".encode("utf-8")))

        result = asyncio.run(split_uploaded_document(upload))

        self.assertEqual(result["file_name"], "notice.txt")
        self.assertEqual(result["chunk_count"], 1)
        self.assertEqual(result["chunks"][0]["chunk_index"], 0)
        self.assertEqual(result["chunks"][0]["content"], "校园通知")
