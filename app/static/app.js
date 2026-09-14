const fileInput = document.querySelector("#file-input");
const dropZone = document.querySelector("#drop-zone");
const fileCard = document.querySelector("#file-card");
const fileName = document.querySelector("#file-name");
const fileMeta = document.querySelector("#file-meta");
const indexButton = document.querySelector("#index-button");
const indexResult = document.querySelector("#index-result");
const questionForm = document.querySelector("#question-form");
const questionInput = document.querySelector("#question-input");
const sendButton = document.querySelector("#send-button");
const conversation = document.querySelector("#conversation");
const emptyConversation = document.querySelector("#empty-conversation");
const serviceState = document.querySelector("#service-state");

let selectedFile = null;
let hasIndex = false;

function formatFileSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  return `${(bytes / 1024).toFixed(1)} KB`;
}

function setButtonLoading(button, label, loading) {
  button.disabled = loading || (button === indexButton && !selectedFile);
  button.querySelector("span")?.replaceChildren(document.createTextNode(label));
}

function showIndexResult(message, isError = false) {
  indexResult.hidden = false;
  indexResult.textContent = message;
  indexResult.classList.toggle("is-error", isError);
}

function selectFile(file) {
  if (!file) return;
  const name = file.name.toLowerCase();
  if (!name.endsWith(".txt") && !name.endsWith(".md")) {
    showIndexResult("暂只支持 TXT 与 Markdown 文件。", true);
    return;
  }
  selectedFile = file;
  fileCard.classList.remove("is-empty");
  fileName.textContent = file.name;
  fileMeta.textContent = `${formatFileSize(file.size)} · 等待建立索引`;
  indexButton.disabled = false;
  indexResult.hidden = true;
}

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
      <div><strong>${escapeHtml(source.source_file)}</strong><span>段落 ${source.chunk_index} · 相似度 ${Number(source.score).toFixed(2)}</span></div>
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
  event.preventDefault();
  dropZone.classList.add("is-dragging");
}));
["dragleave", "drop"].forEach((eventName) => dropZone.addEventListener(eventName, (event) => {
  event.preventDefault();
  dropZone.classList.remove("is-dragging");
}));
dropZone.addEventListener("drop", (event) => selectFile(event.dataTransfer.files[0]));

indexButton.addEventListener("click", async () => {
  if (!selectedFile) return;
  setButtonLoading(indexButton, "正在建立索引…", true);
  const formData = new FormData();
  formData.append("file", selectedFile);
  try {
    const response = await fetch("/documents/index", { method: "POST", body: formData });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "建立索引失败");
    hasIndex = true;
    questionInput.disabled = false;
    sendButton.disabled = false;
    fileMeta.textContent = `${formatFileSize(selectedFile.size)} · 已建立 ${payload.chunk_count} 个段落`;
    showIndexResult(`索引完成：${payload.file_name} 已加入知识库，当前共有 ${payload.indexed_chunk_count} 个段落。`);
  } catch (error) {
    showIndexResult(error.message || "建立索引失败，请稍后重试。", true);
  } finally {
    setButtonLoading(indexButton, "建立索引", false);
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
    appendError(error.message || "问答失败，请稍后重试。。");
  } finally {
    sendButton.disabled = false;
  }
});

checkService();
