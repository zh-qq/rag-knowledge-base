from fastapi import FastAPI, File, HTTPException, UploadFile

from app.document_reader import DocumentReadError, read_text_document

app = FastAPI(title="RAG 知识库问答系统")
PREVIEW_LENGTH = 500


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "message": "服务正常"}


@app.post("/documents/preview")
async def preview_document(file: UploadFile = File(...)) -> dict[str, str | int]:
    """读取上传的文本文件，并返回前 500 个字符供用户确认。"""
    filename = file.filename or ""

    try:
        content = await file.read()
        text = read_text_document(filename, content)
    except DocumentReadError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    finally:
        await file.close()

    return {
        "file_name": filename,
        "characters": len(text),
        "preview": text[:PREVIEW_LENGTH],
    }
