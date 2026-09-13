from fastapi import FastAPI

app = FastAPI(title="RAG 知识库问答系统")


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "message": "服务正常"}
