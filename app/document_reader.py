from io import BytesIO
from pathlib import Path
from typing import Final

from pypdf import PdfReader
from pypdf.errors import PdfReadError

ALLOWED_SUFFIXES: Final = {".txt", ".md", ".pdf"}


class DocumentReadError(ValueError):
    """文档内容不符合当前读取规则时抛出。"""


def read_text_document(filename: str, content: bytes) -> str:
    """读取 TXT、Markdown 或含文本 PDF 文件并返回文本内容。"""
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise DocumentReadError("暂只支持 .txt、.md 和 .pdf 文件")

    if not content:
        raise DocumentReadError("文件内容不能为空")

    if suffix == ".pdf":
        return read_pdf_document(content)

    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise DocumentReadError("文件必须使用 UTF-8 编码") from error


def read_pdf_document(content: bytes) -> str:
    """提取含文本 PDF 的所有页面内容；不支持加密或扫描型 PDF。"""
    try:
        reader = PdfReader(BytesIO(content))
        if reader.is_encrypted:
            raise DocumentReadError("暂不支持加密的 PDF 文件")
        text = "\n".join(page.extract_text() or "" for page in reader.pages).strip()
    except PdfReadError as error:
        raise DocumentReadError("PDF 文件损坏或无法读取") from error

    if not text:
        raise DocumentReadError("PDF 未检测到可提取文本，请上传含文字的 PDF 文件")
    return text
