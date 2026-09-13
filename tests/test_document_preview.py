import asyncio
from io import BytesIO
import unittest

from fastapi import HTTPException, UploadFile

from app.main import preview_document


class DocumentPreviewTests(unittest.TestCase):
    def test_returns_document_preview(self) -> None:
        upload = UploadFile(
            filename="notice.txt",
            file=BytesIO("图书馆开放至晚上十点。".encode("utf-8")),
        )

        result = asyncio.run(preview_document(upload))

        self.assertEqual(result["file_name"], "notice.txt")
        self.assertEqual(result["characters"], 11)
        self.assertEqual(result["preview"], "图书馆开放至晚上十点。")

    def test_returns_clear_error_for_unsupported_file(self) -> None:
        upload = UploadFile(filename="notice.pdf", file=BytesIO(b"content"))

        with self.assertRaises(HTTPException) as context:
            asyncio.run(preview_document(upload))

        self.assertEqual(context.exception.status_code, 400)
        self.assertEqual(context.exception.detail, "暂只支持 .txt 和 .md 文件")
