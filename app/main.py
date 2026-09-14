from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pathlib import Path

from app.chat_client import ChatError, answer_from_context
from app.document_reader import DocumentReadError, read_text_document
from app.embedding_client import EmbeddingError, embed_texts
from app.knowledge_base_repository import (
    KnowledgeBaseRepositoryError,
    SupabaseKnowledgeBaseRepository,
)
from app.settings import (
    AppSettings,
    SettingsError,
    app_settings_from_values,
    load_app_settings,
    load_chat_settings,
    load_embedding_settings,
    load_rerank_settings,
    load_supabase_settings,
)
from app.rerank_client import RerankError, rerank_results
from app.text_chunker import DocumentChunk, TextChunkError, split_document
from app.vector_store import SearchResult, VectorStore, VectorStoreError

app = FastAPI(title="RAG 知识库问答系统")
PREVIEW_LENGTH = 500
FAISS_CANDIDATE_LIMIT = 10
RERANK_RESULT_LIMIT = 3
vector_store: VectorStore | None = None
cloud_repository: SupabaseKnowledgeBaseRepository | None = None
active_knowledge_base_id: int | None = None
runtime_settings: AppSettings = app_settings_from_values({})
STATIC_DIR = Path(__file__).parent / "static"
DATA_DIR = Path(__file__).parent.parent / "data"
INDEX_PATH = DATA_DIR / "knowledge_base.faiss"
METADATA_PATH = DATA_DIR / "chunks.json"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class AskRequest(BaseModel):
    question: str
    knowledge_base_id: int | None = None


@app.on_event("startup")
def restore_vector_store() -> None:
    """服务启动时优先启用云端知识库；未配置时保留本地模式。"""
    global active_knowledge_base_id, cloud_repository, runtime_settings, vector_store
    runtime_settings = load_app_settings()
    try:
        cloud_repository = SupabaseKnowledgeBaseRepository(load_supabase_settings())
        vector_store = None
    except SettingsError:
        cloud_repository = None
        vector_store = VectorStore.load(INDEX_PATH, METADATA_PATH)
        if runtime_settings.public_demo_mode:
            raise RuntimeError("公开演示模式需要配置 Supabase 云端知识库")
        return

    if runtime_settings.public_demo_mode:
        try:
            knowledge_base = cloud_repository.get_knowledge_base_by_name(
                runtime_settings.public_demo_knowledge_base_name
            )
            if knowledge_base is None:
                raise RuntimeError("未找到公开演示知识库")
            vector_store = cloud_repository.load_vector_store(knowledge_base.id)
        except KnowledgeBaseRepositoryError as error:
            raise RuntimeError("加载公开演示知识库失败") from error
        if vector_store is None:
            raise RuntimeError("公开演示知识库暂无可用资料")
        active_knowledge_base_id = knowledge_base.id


@app.get("/", include_in_schema=False)
def serve_app() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health_check() -> dict[str, str | bool]:
    return {
        "status": "ok",
        "message": "服务正常",
        "public_demo_mode": runtime_settings.public_demo_mode,
    }


@app.get("/knowledge-base/status")
def knowledge_base_status() -> dict[str, int | str | bool | None]:
    """返回当前已加载的知识库段落数量。"""
    return {
        "mode": "cloud" if cloud_repository else "local",
        "knowledge_base_id": active_knowledge_base_id,
        "indexed_chunk_count": vector_store.count if vector_store else 0,
        "public_demo_mode": runtime_settings.public_demo_mode,
    }


@app.get("/knowledge-bases")
def list_knowledge_bases() -> dict:
    """列出可选择的知识库；未配置 Supabase 时提供单个本地知识库。"""
    if cloud_repository is None:
        return {
            "mode": "local",
            "active_knowledge_base_id": 0,
            "knowledge_bases": [{"id": 0, "name": "本地默认知识库"}],
        }
    if runtime_settings.public_demo_mode:
        return {
            "mode": "cloud",
            "public_demo_mode": True,
            "protected_knowledge_base_name": runtime_settings.public_demo_knowledge_base_name,
            "active_knowledge_base_id": active_knowledge_base_id,
            "knowledge_bases": [
                {
                    "id": active_knowledge_base_id,
                    "name": runtime_settings.public_demo_knowledge_base_name,
                }
            ],
        }
    try:
        knowledge_bases = cloud_repository.list_knowledge_bases()
    except KnowledgeBaseRepositoryError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    return {
        "mode": "cloud",
        "public_demo_mode": False,
        "protected_knowledge_base_name": runtime_settings.public_demo_knowledge_base_name,
        "active_knowledge_base_id": active_knowledge_base_id,
        "knowledge_bases": [{"id": item.id, "name": item.name} for item in knowledge_bases],
    }


class KnowledgeBaseCreateRequest(BaseModel):
    name: str


@app.post("/knowledge-bases")
def create_knowledge_base(request: KnowledgeBaseCreateRequest) -> dict[str, int | str]:
    """创建一个新的云端知识库，并自动切换到它。"""
    global active_knowledge_base_id, vector_store

    ensure_writable()
    name = request.name.strip()
    if not name or len(name) > 50:
        raise HTTPException(status_code=400, detail="知识库名称长度需要在 1 到 50 个字符之间")
    if cloud_repository is None:
        raise HTTPException(status_code=400, detail="请先配置 Supabase 云端知识库")
    try:
        knowledge_base = cloud_repository.create_knowledge_base(name)
    except KnowledgeBaseRepositoryError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error

    active_knowledge_base_id = knowledge_base.id
    vector_store = None
    return {"id": knowledge_base.id, "name": knowledge_base.name, "indexed_chunk_count": 0}


@app.post("/knowledge-bases/{knowledge_base_id}/select")
def select_knowledge_base(knowledge_base_id: int) -> dict[str, int]:
    """切换知识库，并从云端段落和向量重建当前 FAISS 索引。"""
    global active_knowledge_base_id, vector_store
    ensure_writable()

    if cloud_repository is None:
        if knowledge_base_id != 0:
            raise HTTPException(status_code=400, detail="本地模式只有默认知识库")
        return {"id": 0, "indexed_chunk_count": vector_store.count if vector_store else 0}
    try:
        vector_store = cloud_repository.load_vector_store(knowledge_base_id)
    except KnowledgeBaseRepositoryError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    active_knowledge_base_id = knowledge_base_id
    return {"id": knowledge_base_id, "indexed_chunk_count": vector_store.count if vector_store else 0}


@app.delete("/knowledge-bases/{knowledge_base_id}")
def delete_knowledge_base(knowledge_base_id: int) -> dict[str, str]:
    """删除当前云端知识库及其级联文档；公开样本库不可删除。"""
    global active_knowledge_base_id, vector_store
    ensure_writable()

    if cloud_repository is None:
        raise HTTPException(status_code=400, detail="本地模式不能删除默认知识库")
    if active_knowledge_base_id != knowledge_base_id:
        raise HTTPException(status_code=400, detail="只能删除当前选择的知识库")
    try:
        protected_knowledge_base = cloud_repository.get_knowledge_base_by_name(
            runtime_settings.public_demo_knowledge_base_name
        )
        if protected_knowledge_base and protected_knowledge_base.id == knowledge_base_id:
            raise HTTPException(status_code=403, detail="公开演示知识库受保护，不能删除")
        cloud_repository.delete_knowledge_base(knowledge_base_id)
    except KnowledgeBaseRepositoryError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error

    active_knowledge_base_id = None
    vector_store = None
    return {"message": "知识库已删除"}


@app.delete("/knowledge-base")
def clear_knowledge_base() -> dict[str, str | int]:
    """清空内存和本地保存的知识库文件。"""
    global vector_store
    ensure_writable()

    if cloud_repository:
        if active_knowledge_base_id is None:
            raise HTTPException(status_code=400, detail="请先选择一个知识库")
        try:
            cloud_repository.clear_knowledge_base(active_knowledge_base_id)
        except KnowledgeBaseRepositoryError as error:
            raise HTTPException(status_code=502, detail=str(error)) from error
    else:
        try:
            INDEX_PATH.unlink(missing_ok=True)
            METADATA_PATH.unlink(missing_ok=True)
        except OSError as error:
            raise HTTPException(status_code=500, detail="清空本地知识库失败") from error

    vector_store = None
    return {"message": "知识库已清空", "indexed_chunk_count": 0}


async def read_uploaded_text(file: UploadFile) -> tuple[str, str]:
    """读取上传文件；始终在请求结束前关闭临时文件。"""
    filename = file.filename or ""

    try:
        content = bytearray()
        while block := await file.read(64 * 1024):
            content.extend(block)
            if len(content) > runtime_settings.max_upload_bytes:
                raise HTTPException(
                    status_code=400,
                    detail=f"上传文件不能超过 {runtime_settings.max_upload_bytes // (1024 * 1024)}MB",
                )
        return filename, read_text_document(filename, bytes(content))
    except DocumentReadError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    finally:
        await file.close()


@app.post("/documents/preview")
async def preview_document(file: UploadFile = File(...)) -> dict[str, str | int]:
    """读取上传的文本文件，并返回前 500 个字符供用户确认。"""
    ensure_writable()
    filename, text = await read_uploaded_text(file)
    ensure_non_blank_text(text)

    return {
        "file_name": filename,
        "characters": len(text),
        "preview": text[:PREVIEW_LENGTH],
    }


@app.post("/documents/chunks")
async def split_uploaded_document(file: UploadFile = File(...)) -> dict:
    """读取上传文件并返回默认规则切分后的文本段落。"""
    ensure_writable()
    filename, text = await read_uploaded_text(file)
    chunks = split_text(filename, text)

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


def add_to_vector_store(chunks: list[DocumentChunk], vectors: list[list[float]]) -> VectorStore:
    """首次写入时根据云端向量维度创建索引，后续文档加入同一索引。"""
    global vector_store

    if not vectors:
        raise VectorStoreError("云端未返回文档向量")
    if vector_store is None:
        vector_store = VectorStore(dimension=len(vectors[0]))

    vector_store.add(chunks, vectors)
    return vector_store


def save_vector_store(store: VectorStore) -> None:
    """保存索引，供下次服务启动时自动恢复。"""
    store.save(INDEX_PATH, METADATA_PATH)


@app.post("/documents/index")
async def index_uploaded_document(
    file: UploadFile = File(...), knowledge_base_id: int | None = Form(default=None)
) -> dict[str, str | int]:
    """上传文档、切分文本并写入内存向量索引。"""
    ensure_writable()
    filename, text = await read_uploaded_text(file)
    chunks = split_text(filename, text)

    try:
        vectors = embed_texts(
            [chunk.content for chunk in chunks],
            load_embedding_settings(),
            runtime_settings.embedding_batch_size,
        )
        if cloud_repository:
            if active_knowledge_base_id is None or knowledge_base_id != active_knowledge_base_id:
                raise HTTPException(status_code=400, detail="请先选择要写入的知识库")
            cloud_repository.save_document(active_knowledge_base_id, filename, chunks, vectors)
        store = add_to_vector_store(chunks, vectors)
        if cloud_repository is None:
            save_vector_store(store)
    except SettingsError as error:
        raise HTTPException(status_code=500, detail="云端向量配置不完整") from error
    except KnowledgeBaseRepositoryError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except EmbeddingError as error:
        raise HTTPException(status_code=502, detail="云端向量服务调用失败") from error
    except VectorStoreError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error

    return {
        "file_name": filename,
        "chunk_count": len(chunks),
        "indexed_chunk_count": store.count,
    }


@app.get("/search")
def search_documents(query: str, limit: int = 3, knowledge_base_id: int | None = None) -> dict:
    """将用户问题向量化，并返回最相关的文本段落。"""
    validate_question(query)
    if limit <= 0 or limit > 10:
        raise HTTPException(status_code=400, detail="返回数量必须在 1 到 10 之间")
    store = resolve_vector_store(knowledge_base_id)
    if store is None:
        raise HTTPException(status_code=400, detail="尚未建立知识库索引")

    try:
        vectors = embed_texts([query], load_embedding_settings(), runtime_settings.embedding_batch_size)
        results = store.search(vectors[0], limit)
    except SettingsError as error:
        raise HTTPException(status_code=500, detail="云端向量配置不完整") from error
    except EmbeddingError as error:
        raise HTTPException(status_code=502, detail="云端向量服务调用失败") from error
    except VectorStoreError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error

    return {
        "query": query,
        "results": [serialize_search_result(result) for result in results],
    }


def serialize_search_result(
    result: SearchResult, citation_index: int | None = None
) -> dict[str, str | int | float]:
    serialized = {
        "source_file": result.source_file,
        "chunk_index": result.chunk_index,
        "content": result.content,
        "score": result.score,
    }
    if citation_index is not None:
        serialized["citation_index"] = citation_index
    return serialized


@app.post("/ask")
def ask_question(request: AskRequest) -> dict:
    """检索相关资料后，调用对话模型生成带来源的回答。"""
    validate_question(request.question)
    store = resolve_vector_store(request.knowledge_base_id)
    if store is None:
        raise HTTPException(status_code=400, detail="尚未建立知识库索引")

    try:
        query_vector = embed_texts(
            [request.question], load_embedding_settings(), runtime_settings.embedding_batch_size
        )[0]
        candidates = store.search(query_vector, min(FAISS_CANDIDATE_LIMIT, store.count))
        results = rerank_results(
            request.question,
            candidates,
            load_rerank_settings(),
            min(RERANK_RESULT_LIMIT, len(candidates)),
        )
        answer = answer_from_context(request.question, results, load_chat_settings())
    except SettingsError as error:
        raise HTTPException(status_code=500, detail="云端模型配置不完整") from error
    except EmbeddingError as error:
        raise HTTPException(status_code=502, detail="云端向量服务调用失败") from error
    except RerankError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except ChatError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except VectorStoreError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error

    return {
        "answer": answer,
        "sources": [
            serialize_search_result(result, citation_index)
            for citation_index, result in enumerate(results, start=1)
        ],
    }


def ensure_writable() -> None:
    """公开演示服务只允许读取，禁止任何改变知识库状态的请求。"""
    if runtime_settings.public_demo_mode:
        raise HTTPException(status_code=403, detail="公开 Demo 为只读模式，不能修改知识库")


def ensure_non_blank_text(text: str) -> None:
    if not text.strip():
        raise HTTPException(status_code=400, detail="待切分文本不能为空")


def split_text(filename: str, text: str) -> list[DocumentChunk]:
    """切分文本并阻止单次请求生成过多段落。"""
    try:
        chunks = split_document(filename, text)
    except TextChunkError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    if len(chunks) > runtime_settings.max_chunk_count:
        raise HTTPException(
            status_code=400,
            detail=f"文档切分后不能超过 {runtime_settings.max_chunk_count} 个段落",
        )
    return chunks


def validate_question(question: str) -> None:
    if not question.strip():
        raise HTTPException(status_code=400, detail="问题不能为空")
    if len(question) > runtime_settings.max_question_length:
        raise HTTPException(
            status_code=400,
            detail=f"问题不能超过 {runtime_settings.max_question_length} 个字符",
        )


def resolve_vector_store(knowledge_base_id: int | None = None) -> VectorStore | None:
    """公开模式始终使用固定样本库；非公开接口可按需读取指定云端知识库。"""
    if runtime_settings.public_demo_mode or knowledge_base_id is None:
        return vector_store
    if cloud_repository is None:
        if knowledge_base_id != 0:
            raise HTTPException(status_code=400, detail="本地模式只有默认知识库")
        return vector_store
    try:
        return cloud_repository.load_vector_store(knowledge_base_id)
    except KnowledgeBaseRepositoryError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
