from fastapi import FastAPI, File, HTTPException, UploadFile

from app.document_reader import DocumentReadError, read_text_document
from app.text_chunker import DocumentChunk, split_document

app = FastAPI(title="RAG 知识库问答系统")
PREVIEW_LENGTH = 500


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "message": "服务正常"}


async def read_uploaded_text(file: UploadFile) -> tuple[str, str]:
    """读取上传文件；始终在请求结束前关闭临时文件。"""
    filename = file.filename or ""

    try:
        content = await file.read()
        return filename, read_text_document(filename, content)
    except DocumentReadError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    finally:
        await file.close()


@app.post("/documents/preview")
async def preview_document(file: UploadFile = File(...)) -> dict[str, str | int]:
    """读取上传的文本文件，并返回前 500 个字符供用户确认。"""
    filename, text = await read_uploaded_text(file)

    return {
        "file_name": filename,
        "characters": len(text),
        "preview": text[:PREVIEW_LENGTH],
    }


@app.post("/documents/chunks")
async def split_uploaded_document(file: UploadFile = File(...)) -> dict:
    """读取上传文件并返回默认规则切分后的文本段落。"""
    filename, text = await read_uploaded_text(file)
    chunks = split_document(filename, text)

    return {
        "file_name": filename,
        "chunk_count": len(chunks),
        "chunks": [serialize_chunk(chunk) for chunk in chunks],
    }


def serialize_chunk(chunk: DocumentChunk) -> dict[str, str | int]:
    return {
        "source_file": chunk.source_file,
        "chunk_index": chunk.chunk_index,
        "content": chunk.content,
    }
