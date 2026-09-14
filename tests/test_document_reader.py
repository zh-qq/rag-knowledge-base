from io import BytesIO
import unittest

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from app.document_reader import DocumentReadError, read_text_document


def create_text_pdf(text: str) -> bytes:
    """构造带一行英文文本的内存 PDF，供真实解析测试使用。"""
    writer = PdfWriter()
    page = writer.add_blank_page(width=595, height=842)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})}
    )
    content = DecodedStreamObject()
    content.set_data(f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("ascii"))
    page[NameObject("/Contents")] = writer._add_object(content)
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


class DocumentReaderTests(unittest.TestCase):
    def test_reads_txt_file(self) -> None:
        text = read_text_document("notice.txt", "图书馆开放至晚上十点。".encode())

        self.assertEqual(text, "图书馆开放至晚上十点。")

    def test_reads_markdown_file(self) -> None:
        text = read_text_document("guide.md", "# 使用说明".encode("utf-8"))

        self.assertEqual(text, "# 使用说明")

    def test_reads_pdf_file(self) -> None:
        text = read_text_document("notice.pdf", create_text_pdf("Library closes at ten."))

        self.assertEqual(text, "Library closes at ten.")

    def test_rejects_unsupported_file_type(self) -> None:
        with self.assertRaisesRegex(DocumentReadError, "暂只支持"):
            read_text_document("manual.docx", b"content")

    def test_rejects_empty_file(self) -> None:
        with self.assertRaisesRegex(DocumentReadError, "不能为空"):
            read_text_document("empty.txt", b"")

    def test_rejects_non_utf8_file(self) -> None:
        with self.assertRaisesRegex(DocumentReadError, "UTF-8"):
            read_text_document("legacy.txt", b"\xff\xfe")

    def test_rejects_pdf_without_extractable_text(self) -> None:
        empty_pdf = PdfWriter()
        empty_pdf.add_blank_page(width=595, height=842)
        buffer = BytesIO()
        empty_pdf.write(buffer)

        with self.assertRaisesRegex(DocumentReadError, "未检测到可提取文本"):
            read_text_document("scan.pdf", buffer.getvalue())

    def test_rejects_encrypted_pdf(self) -> None:
        encrypted_pdf = PdfWriter()
        encrypted_pdf.add_blank_page(width=595, height=842)
        encrypted_pdf.encrypt("password")
        buffer = BytesIO()
        encrypted_pdf.write(buffer)

        with self.assertRaisesRegex(DocumentReadError, "不支持加密"):
            read_text_document("secret.pdf", buffer.getvalue())

    def test_rejects_broken_pdf(self) -> None:
        with self.assertRaisesRegex(DocumentReadError, "损坏或无法读取"):
            read_text_document("broken.pdf", b"not a PDF")
