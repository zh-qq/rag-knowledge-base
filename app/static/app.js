const fileInput = document.querySelector("#file-input");
const dropZone = document.querySelector("#drop-zone");
const fileCard = document.querySelector("#file-card");
const fileName = document.querySelector("#file-name");
const fileMeta = document.querySelector("#file-meta");
const indexButton = document.querySelector("#index-button");
const clearButton = document.querySelector("#clear-button");
const indexResult = document.querySelector("#index-result");
const questionForm = document.querySelector("#question-form");
const questionInput = document.querySelector("#question-input");
const sendButton = document.querySelector("#send-button");
const conversation = document.querySelector("#conversation");
const emptyConversation = document.querySelector("#empty-conversation");
const serviceState = document.querySelector("#service-state");
const knowledgeBaseSelect = document.querySelector("#knowledge-base-select");
const knowledgeBaseName = document.querySelector("#knowledge-base-name");
const createKnowledgeBaseButton = document.querySelector("#create-knowledge-base-button");
const knowledgeBaseHint = document.querySelector("#knowledge-base-hint");

let selectedFile = null;
let hasIndex = false;
let cloudMode = false;
let activeKnowledgeBaseId = null;
let publicDemoMode = false;

function formatFileSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  return `${(bytes / 1024).toFixed(1)} KB`;
}

function setButtonLoading(button, label, loading) {
  button.disabled = loading || publicDemoMode || (button === indexButton && (!selectedFile || (cloudMode && activeKnowledgeBaseId === null)));
  button.querySelector("span")?.replaceChildren(document.createTextNode(label));
}

function updateIndexButton() {
  indexButton.disabled = publicDemoMode || !selectedFile || (cloudMode && activeKnowledgeBaseId === null);
}

function showIndexResult(message, isError = false) {
  indexResult.hidden = false;
  indexResult.textContent = message;
  indexResult.classList.toggle("is-error", isError);
}

function setQuestionAvailability(enabled) {
  hasIndex = enabled;
  questionInput.disabled = !enabled;
  sendButton.disabled = !enabled;
  clearButton.disabled = publicDemoMode || !enabled;
}

function resetSelectedFile() {
  selectedFile = null;
  fileInput.value = "";
  fileCard.classList.add("is-empty");
  fileName.textContent = "尚未选择文件";
  fileMeta.textContent = "请选择一份资料开始建立知识库";
  updateIndexButton();
}

function resetConversation() {
  conversation.replaceChildren();
  const emptyState = document.createElement("div");
  emptyState.className = "empty-conversation";
  emptyState.id = "empty-conversation";
  emptyState.textContent = "建立索引后，在这里提出你的问题。";
  conversation.append(emptyState);
}

function selectFile(file) {
  if (publicDemoMode) {
    showIndexResult("公开 Demo 为只读模式，不能上传资料。", true);
    return;
  }
  if (!file) return;
  const name = file.name.toLowerCase();
  if (!name.endsWith(".txt") && !name.endsWith(".md") && !name.endsWith(".pdf")) {
    showIndexResult("暂只支持 TXT、Markdown 与 PDF 文件。", true);
    return;
  }
  selectedFile = file;
  fileCard.classList.remove("is-empty");
  fileName.textContent = file.name;
  fileMeta.textContent = `${formatFileSize(file.size)} · 等待建立索引`;
  updateIndexButton();
  indexResult.hidden = true;
}

async function activateKnowledgeBase(id, showMessage = true) {
  try {
    const response = await fetch(`/knowledge-bases/${id}/select`, { method: "POST" });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "切换知识库失败");
    activeKnowledgeBaseId = Number(payload.id);
    knowledgeBaseSelect.value = String(activeKnowledgeBaseId);
    setQuestionAvailability(payload.indexed_chunk_count > 0);
    updateIndexButton();
    if (showMessage) showIndexResult(`已切换知识库，当前共有 ${payload.indexed_chunk_count} 个段落。`);
  } catch (error) {
    activeKnowledgeBaseId = null;
    setQuestionAvailability(false);
    updateIndexButton();
    showIndexResult(error.message || "切换知识库失败，请稍后重试。", true);
  }
}

async function loadKnowledgeBases() {
  try {
    const response = await fetch("/knowledge-bases");
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "读取知识库列表失败");
    cloudMode = payload.mode === "cloud";
    publicDemoMode = payload.public_demo_mode === true;
    setPublicDemoMode(publicDemoMode);
    knowledgeBaseSelect.replaceChildren();
    const knowledgeBases = payload.knowledge_bases || [];
    if (!knowledgeBases.length) {
      knowledgeBaseSelect.append(new Option("请先新建知识库", ""));
      knowledgeBaseSelect.disabled = true;
      knowledgeBaseHint.textContent = "云端模式：请先输入名称并新建知识库。";
      setQuestionAvailability(false);
      updateIndexButton();
      return;
    }
    knowledgeBases.forEach((item) => knowledgeBaseSelect.append(new Option(item.name, String(item.id))));
    knowledgeBaseSelect.disabled = publicDemoMode;
    knowledgeBaseHint.textContent = publicDemoMode
      ? "公开 Demo 为只读模式，正在使用固定的公开演示知识库。"
      : (cloudMode ? "云端模式：资料会保存到当前选择的知识库。" : "本地模式：配置 Supabase 后可创建多个云端知识库。");
    const selectedId = payload.active_knowledge_base_id ?? knowledgeBases[0].id;
    if (publicDemoMode) {
      activeKnowledgeBaseId = Number(selectedId);
      knowledgeBaseSelect.value = String(activeKnowledgeBaseId);
      const statusResponse = await fetch("/knowledge-base/status");
      const status = await statusResponse.json();
      if (!statusResponse.ok) throw new Error(status.detail || "读取知识库状态失败");
      setQuestionAvailability(status.indexed_chunk_count > 0);
      showIndexResult("公开 Demo 为只读模式：可以直接向样本知识库提问。");
      return;
    }
    await activateKnowledgeBase(selectedId, false);
  } catch (error) {
    knowledgeBaseHint.textContent = "知识库列表读取失败。";
    showIndexResult(error.message || "知识库列表读取失败，请稍后重试。", true);
  }
}

knowledgeBaseSelect.addEventListener("change", () => {
  if (knowledgeBaseSelect.value) activateKnowledgeBase(knowledgeBaseSelect.value);
});

createKnowledgeBaseButton.addEventListener("click", async () => {
  if (publicDemoMode) return;
  const name = knowledgeBaseName.value.trim();
  if (!name) {
    showIndexResult("请输入新知识库名称。", true);
    return;
  }
  createKnowledgeBaseButton.disabled = true;
  try {
    const response = await fetch("/knowledge-bases", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "创建知识库失败");
    knowledgeBaseName.value = "";
    await loadKnowledgeBases();
    showIndexResult(`已创建并切换到“${payload.name}”。`);
  } catch (error) {
    showIndexResult(error.message || "创建知识库失败，请稍后重试。", true);
  } finally {
    createKnowledgeBaseButton.disabled = false;
  }
});

function icon(name) {
  if (name === "book") return '<svg aria-hidden="true" viewBox="0 0 24 24" fill="none"><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v16H6.5A2.5 2.5 0 0 0 4 21V5.5Z" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/><path d="M4 5.5A2.5 2.5 0 0 1 6.5 8H20M9 7v12" stroke="currentColor" stroke-width="1.7"/></svg>';
  return '<svg aria-hidden="true" viewBox="0 0 24 24" fill="none"><path d="M14 2.75H6.75A2.75 2.75 0 0 0 4 5.5v13A2.75 2.75 0 0 0 6.75 21h10.5A2.75 2.75 0 0 0 20 18.25V8.75L14 2.75Z" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/><path d="M14 2.75v6h6" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/></svg>';
}

function appendAnswer(question, payload) {
  emptyConversation?.remove();
  const questionNode = document.createElement("div");
  questionNode.className = "message user";
  questionNode.textContent = question;

  const answerNode = document.createElement("article");
  answerNode.className = "answer-card";
  const sources = payload.sources.map((source) => `
    <div class="source-item">
      ${icon("file")}
      <div>
        <strong>[${source.citation_index}] ${escapeHtml(source.source_file)}</strong>
        <span>段落 ${Number(source.chunk_index) + 1} · 相关度 ${Number(source.score).toFixed(2)}</span>
        <small>${escapeHtml(source.content.slice(0, 120))}${source.content.length > 120 ? "…" : ""}</small>
      </div>
    </div>`).join("");
  answerNode.innerHTML = `
    <h2 class="answer-title">${icon("book")}<span>回答</span></h2>
    <div class="answer-content">${escapeHtml(payload.answer)}</div>
    <section class="source-list"><h3>来源</h3>${sources}</section>`;

  conversation.append(questionNode, answerNode);
  conversation.scrollTop = conversation.scrollHeight;
}

function appendError(message) {
  emptyConversation?.remove();
  const node = document.createElement("div");
  node.className = "message-error";
  node.textContent = message;
  conversation.append(node);
  conversation.scrollTop = conversation.scrollHeight;
}

function setPublicDemoMode(enabled) {
  publicDemoMode = enabled;
  knowledgeBaseName.disabled = enabled || !cloudMode;
  createKnowledgeBaseButton.disabled = enabled || !cloudMode;
  knowledgeBaseName.hidden = enabled;
  createKnowledgeBaseButton.hidden = enabled;
  dropZone.hidden = enabled;
  fileCard.hidden = enabled;
  indexButton.parentElement.hidden = enabled;
  if (enabled) resetSelectedFile();
}

function escapeHtml(value) {
  return String(value).replace(/[&<>'"]/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#039;", '"': "&quot;" })[character]);
}

async function checkService() {
  try {
    const response = await fetch("/health");
    if (!response.ok) throw new Error();
    serviceState.className = "service-state is-ready";
    serviceState.lastElementChild.textContent = "服务正常";
  } catch {
    serviceState.className = "service-state is-error";
    serviceState.lastElementChild.textContent = "服务不可用";
  }
}

fileInput.addEventListener("change", (event) => selectFile(event.target.files[0]));
["dragenter", "dragover"].forEach((eventName) => dropZone.addEventListener(eventName, (event) => {
  if (publicDemoMode) return;
  event.preventDefault();
  dropZone.classList.add("is-dragging");
}));
["dragleave", "drop"].forEach((eventName) => dropZone.addEventListener(eventName, (event) => {
  if (publicDemoMode) return;
  event.preventDefault();
  dropZone.classList.remove("is-dragging");
}));
dropZone.addEventListener("drop", (event) => {
  if (!publicDemoMode) selectFile(event.dataTransfer.files[0]);
});

indexButton.addEventListener("click", async () => {
  if (publicDemoMode || !selectedFile) return;
  setButtonLoading(indexButton, "正在建立索引…", true);
  const formData = new FormData();
  formData.append("file", selectedFile);
  if (cloudMode && activeKnowledgeBaseId !== null) formData.append("knowledge_base_id", String(activeKnowledgeBaseId));
  try {
    const response = await fetch("/documents/index", { method: "POST", body: formData });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "建立索引失败");
    setQuestionAvailability(true);
    fileMeta.textContent = `${formatFileSize(selectedFile.size)} · 已建立 ${payload.chunk_count} 个段落`;
    showIndexResult(`索引完成：${payload.file_name} 已加入知识库，当前共有 ${payload.indexed_chunk_count} 个段落。`);
  } catch (error) {
    showIndexResult(error.message || "建立索引失败，请稍后重试。", true);
  } finally {
    setButtonLoading(indexButton, "建立索引", false);
  }
});

clearButton.addEventListener("click", async () => {
  if (publicDemoMode) return;
  if (!window.confirm("确定清空当前知识库吗？当前知识库中的资料和索引将无法恢复。")) return;
  clearButton.disabled = true;
  try {
    const response = await fetch("/knowledge-base", { method: "DELETE" });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "清空知识库失败");
    setQuestionAvailability(false);
    resetSelectedFile();
    resetConversation();
    showIndexResult("知识库已清空。你可以重新上传资料建立新的索引。");
  } catch (error) {
    clearButton.disabled = false;
    showIndexResult(error.message || "清空知识库失败，请稍后重试。", true);
  }
});

questionForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const question = questionInput.value.trim();
  if (!hasIndex || !question) return;
  sendButton.disabled = true;
  try {
    const response = await fetch("/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, limit: 3 }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "问答失败");
    appendAnswer(question, payload);
    questionInput.value = "";
  } catch (error) {
    appendError(error.message || "问答失败，请稍后重试。");
  } finally {
    sendButton.disabled = false;
  }
});

checkService();
loadKnowledgeBases();
