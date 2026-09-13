import unittest

from app.document_reader import DocumentReadError, read_text_document


class DocumentReaderTests(unittest.TestCase):
    def test_reads_txt_file(self) -> None:
        text = read_text_document("notice.txt", "图书馆开放至晚上十点。".encode())

        self.assertEqual(text, "图书馆开放至晚上十点。")

    def test_reads_markdown_file(self) -> None:
        text = read_text_document("guide.md", "# 使用说明".encode("utf-8"))

        self.assertEqual(text, "# 使用说明")

    def test_rejects_unsupported_file_type(self) -> None:
        with self.assertRaisesRegex(DocumentReadError, "暂只支持"):
            read_text_document("manual.pdf", b"content")

    def test_rejects_empty_file(self) -> None:
        with self.assertRaisesRegex(DocumentReadError, "不能为空"):
            read_text_document("empty.txt", b"")

    def test_rejects_non_utf8_file(self) -> None:
        with self.assertRaisesRegex(DocumentReadError, "UTF-8"):
            read_text_document("legacy.txt", b"\xff\xfe")
