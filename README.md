# RAG 知识库问答系统

一个可公开体验的 RAG（检索增强生成）知识库问答应用。用户上传 TXT、Markdown 或含文字的 PDF 资料后，系统会建立向量索引，并基于检索到的原文生成带来源的回答。

## 在线体验

- 在线 Demo：[rag-knowledge-base-zhqq.onrender.com](https://rag-knowledge-base-zhqq.onrender.com)
- 健康检查：[在线状态](https://rag-knowledge-base-zhqq.onrender.com/health)

> Render 免费服务闲置后会休眠，首次重新访问可能需要等待约一分钟启动。

## 功能

- 上传并读取 TXT、Markdown 与含文字的 PDF 文档。
- 文本自动切分：默认每段 800 字符、重叠 100 字符。
- 调用阿里云百炼兼容接口生成文本向量。
- 使用 FAISS 进行余弦相似度检索。
- 调用 `qwen-plus` 根据检索结果生成中文回答。
- 回答附带来源文件、段落编号和相似度。
- 索引会保存在本地，服务重启时自动恢复。
- 网页端支持建立索引、问答和清空知识库。

## 工作流程

```text
上传资料
  ↓
文档读取 → 文本切分 → 文档向量化 → FAISS 索引
                                           ↓
用户问题 → 问题向量化 → 相似度检索 → qwen-plus 生成回答
                                           ↓
                                      回答 + 来源引用
```

## 技术栈

- 后端：Python、FastAPI、Uvicorn
- 检索：FAISS、NumPy
- 云端模型：阿里云百炼兼容 API、`text-embedding-v2`、`qwen-plus`
- 前端：原生 HTML、CSS、JavaScript
- 部署：Docker、Render、GitHub

## 本地运行

### 1. 克隆项目并创建虚拟环境

```powershell
git clone https://github.com/zh-qq/rag-knowledge-base.git
cd rag-knowledge-base
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. 配置云端模型

将 `.env.example` 复制为 `.env`，然后填写以下值：

```text
DASHSCOPE_API_KEY=<你的百炼 API Key>
DASHSCOPE_BASE_URL=<你的百炼兼容接口地址>
EMBEDDING_MODEL=text-embedding-v2
CHAT_MODEL=qwen-plus
```

`.env` 已被 Git 忽略，禁止提交或分享。

### 3. 启动服务

```powershell
uvicorn app.main:app --reload
```

打开 `http://127.0.0.1:8000`，上传资料后即可开始提问。

## API 概览

| 接口 | 用途 |
| --- | --- |
| `GET /health` | 服务健康检查 |
| `POST /documents/preview` | 预览上传文档 |
| `POST /documents/chunks` | 查看文本切分结果 |
| `POST /documents/index` | 上传并建立知识库索引 |
| `GET /search` | 检索相关文本段落 |
| `POST /ask` | 基于知识库回答问题并返回来源 |
| `DELETE /knowledge-base` | 清空当前知识库 |

## 本地知识库文件

首次建立索引后，系统会生成：

- `data/knowledge_base.faiss`：FAISS 向量索引。
- `data/chunks.json`：段落原文和来源信息。

`data/` 已被 Git 忽略，不会上传到 GitHub。网页中的“清空知识库”操作会删除这些本地索引文件。

## Docker 与 Render 部署

项目提供 `Dockerfile` 和 `render.yaml`，可部署到支持 Docker 的云端平台。

使用 Render 免费部署：

1. 登录 [Render Blueprints](https://dashboard.render.com/blueprints)。
2. 连接 GitHub 仓库 `zh-qq/rag-knowledge-base`。
3. Render 会提示填写 `DASHSCOPE_API_KEY`、`DASHSCOPE_BASE_URL`、`EMBEDDING_MODEL`、`CHAT_MODEL` 四个环境变量。
4. 保持免费计划，创建服务后等待构建完成。

## 当前限制与下一步

- 支持 TXT、Markdown 与含文字的 PDF；暂未支持 Word，也不支持需要 OCR 的扫描型 PDF。
- 当前索引保存在服务本地。Render 免费实例重启或休眠后会丢失已上传资料，需要重新上传。
- 线上 Demo 使用共享的单个知识库，适合演示，不适合多人隔离或长期存储。

下一阶段将考虑：PDF 文档读取、持久化存储、多知识库隔离和更完整的异常提示。
