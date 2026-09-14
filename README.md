# RAG 知识库问答系统

一个可公开体验的 RAG（检索增强生成）知识库问答应用。用户上传 TXT、Markdown 或含文字的 PDF 资料后，系统会建立向量索引，并基于检索到的原文生成带来源的回答。

## 在线体验

- 在线 Demo：[rag-knowledge-base-zhqq.onrender.com](https://rag-knowledge-base-zhqq.onrender.com)
- 健康检查：[在线状态](https://rag-knowledge-base-zhqq.onrender.com/health)

> Render 免费服务闲置后会休眠，首次重新访问可能需要等待约一分钟启动。

## 界面预览

桌面端支持上传 TXT、Markdown 和含文字的 PDF，建立索引后即可在右侧对话区域提问并查看来源。

![桌面端界面](docs/rag-ui-desktop.png)

手机端会自动调整为纵向布局。

![手机端界面](docs/rag-ui-mobile.png)

## 功能

- 上传并读取 TXT、Markdown 与含文字的 PDF 文档。
- 文本自动切分：默认每段 800 字符、重叠 100 字符。
- 调用阿里云百炼兼容接口生成文本向量。
- 使用 FAISS 进行余弦相似度检索。
- 调用 `qwen-plus` 根据检索结果生成中文回答。
- 回答附带来源文件、段落编号和相似度。
- 索引会保存在本地，服务重启时自动恢复。
- 网页端支持建立索引、问答和清空知识库。
- 配置 Supabase 后，支持创建、切换多个云端知识库，并持久保存资料与向量。

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

### 3. 可选：启用 Supabase 云端知识库

1. 在 Supabase 新建免费项目。
2. 打开 SQL Editor，执行仓库中的 [`supabase/schema.sql`](supabase/schema.sql)。
3. 在 `.env` 中补充下列服务端变量：

```text
SUPABASE_URL=https://<你的项目标识>.supabase.co
SUPABASE_SECRET_KEY=<你的 Supabase Secret Key>
```

`SUPABASE_SECRET_KEY` 只能放在 FastAPI 与 Render 的环境变量中，绝不能提交到 GitHub 或写进浏览器代码。未配置这两个变量时，项目仍使用本地单知识库模式。

### 4. 启动服务

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

## 检索效果评估

项目内置 4 条固定中文资料和 4 个对应问题，用于验证向量检索是否把预期来源返回到 Top-3。评测输出两个指标：

- `Recall@3`：预期来源出现在前 3 个结果中的问题比例。
- `MRR@3`：预期来源排名的平均倒数，越接近 1 表示越靠前。

运行真实评测会调用两次云端向量接口，但不会写入本地知识库：

```powershell
.\.venv\Scripts\python.exe -m app.retrieval_evaluation
```

### 最近一次真实评测

2026-09-14 使用配置的 `text-embedding-v2` 对内置 4 条资料和 4 个问题运行评测，结果为：

- `Recall@3 = 1.0000`
- `MRR@3 = 1.0000`

这组数据用于检索回归检查，样本规模很小，不能代表真实业务场景的通用准确率。

## 本地知识库文件

首次建立索引后，系统会生成：

- `data/knowledge_base.faiss`：FAISS 向量索引。
- `data/chunks.json`：段落原文和来源信息。

`data/` 已被 Git 忽略，不会上传到 GitHub。网页中的“清空知识库”操作会删除这些本地索引文件。

启用 Supabase 后，文档段落和向量会保存到云端表中；切换知识库时，服务会重新构建该知识库的内存 FAISS 索引。Render 免费实例即使重启，也能从云端重新加载选中的知识库。

## Docker 与 Render 部署

项目提供 `Dockerfile` 和 `render.yaml`，可部署到支持 Docker 的云端平台。

使用 Render 免费部署：

1. 登录 [Render Blueprints](https://dashboard.render.com/blueprints)。
2. 连接 GitHub 仓库 `zh-qq/rag-knowledge-base`。
3. Render 会提示填写 `DASHSCOPE_API_KEY`、`DASHSCOPE_BASE_URL`、`EMBEDDING_MODEL`、`CHAT_MODEL` 四个环境变量。
4. 保持免费计划，创建服务后等待构建完成。
5. 若启用 Supabase，在 Render 的 Environment 中额外设置 `SUPABASE_URL` 和 `SUPABASE_SECRET_KEY`。

## 当前限制与下一步

- 支持 TXT、Markdown 与含文字的 PDF；暂未支持 Word，也不支持需要 OCR 的扫描型 PDF。
- 未配置 Supabase 时，当前索引保存在服务本地；Render 免费实例重启或休眠后会丢失已上传资料。
- 已配置 Supabase 时可以持久保存多个知识库；当前仍未提供用户登录，因此线上 Demo 的知识库并非按用户隔离。

下一阶段将考虑：持久化存储、多知识库隔离和更完整的异常提示。
