from pathlib import Path
from typing import Final


ALLOWED_SUFFIXES: Final = {".txt", ".md"}


class DocumentReadError(ValueError):
    """文档内容不符合当前读取规则时抛出。"""


def read_text_document(filename: str, content: bytes) -> str:
    """读取 UTF-8 编码的 TXT 或 Markdown 文件并返回文本内容。"""
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise DocumentReadError("暂只支持 .txt 和 .md 文件")

    if not content:
        raise DocumentReadError("文件内容不能为空")

    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise DocumentReadError("文件必须使用 UTF-8 编码") from error
