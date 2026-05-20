from __future__ import annotations


ADMIN_UI_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Memosima Admin</title>
  <style>
    :root {
      color-scheme: light dark;
      --bg: #f6f7f9;
      --fg: #182230;
      --muted: #667085;
      --panel: #fff;
      --border: #d0d5dd;
      --accent: #2563eb;
      --accent-strong: #1d4ed8;
      --danger: #b42318;
      --ok: #067647;
      --warn: #b54708;
      --code: #101828;
      --codebg: #eef2f6;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--fg);
      font: 14px/1.5 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    main { max-width: 1280px; margin: 0 auto; padding: 24px; }
    header { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 20px; }
    h1 { margin: 0; font-size: 1.45rem; line-height: 1.2; }
    h2 { margin: 0 0 14px; font-size: 1rem; line-height: 1.2; }
    label { display: block; color: var(--muted); font-size: .82rem; margin-bottom: 6px; }
    input, select, button, textarea {
      font: inherit;
      border: 1px solid var(--border);
      border-radius: 8px;
    }
    input, select, textarea {
      width: 100%;
      background: var(--panel);
      color: var(--fg);
      padding: 9px 10px;
    }
    textarea { min-height: 74px; resize: vertical; }
    textarea.prompt { min-height: 180px; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace; font-size: .82rem; }
    button {
      background: var(--panel);
      color: var(--fg);
      padding: 8px 11px;
      cursor: pointer;
      white-space: nowrap;
    }
    button.primary { background: var(--accent); border-color: var(--accent); color: #fff; }
    button.primary:hover { background: var(--accent-strong); }
    button.danger { color: var(--danger); }
    button:disabled { cursor: not-allowed; opacity: .55; }
    table { width: 100%; border-collapse: collapse; table-layout: fixed; }
    th, td { border-top: 1px solid var(--border); padding: 9px 8px; text-align: left; vertical-align: top; }
    th { color: var(--muted); font-weight: 600; font-size: .78rem; }
    pre {
      margin: 0;
      background: var(--codebg);
      color: var(--code);
      padding: 10px;
      border-radius: 8px;
      max-height: 360px;
      overflow: auto;
      white-space: pre-wrap;
      word-break: break-word;
    }
    dialog {
      width: min(900px, calc(100vw - 32px));
      border: 1px solid var(--border);
      border-radius: 8px;
      background: var(--panel);
      color: var(--fg);
      padding: 0;
    }
    dialog::backdrop { background: rgba(15, 23, 42, .45); }
    dialog form { padding: 16px; }
    .grid { display: grid; grid-template-columns: 340px minmax(0, 1fr); gap: 16px; align-items: start; }
    .stack { display: grid; gap: 16px; }
    .panel {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 16px;
      box-shadow: 0 1px 2px rgba(16, 24, 40, .04);
    }
    .toolbar { display: flex; gap: 8px; align-items: end; flex-wrap: wrap; margin-bottom: 12px; }
    .field { min-width: 140px; flex: 1 1 140px; }
    .token-row { display: grid; grid-template-columns: minmax(0, 1fr) auto auto; gap: 8px; align-items: end; }
    .muted { color: var(--muted); }
    .status { display: inline-flex; align-items: center; min-height: 24px; padding: 2px 8px; border-radius: 999px; background: var(--codebg); color: var(--muted); font-size: .8rem; }
    .status.succeeded, .status.active, .status.approved { color: var(--ok); }
    .status.failed, .status.rejected { color: var(--danger); }
    .status.pending, .status.running, .status.waiting_user, .status.candidate { color: var(--warn); }
    .actions { display: flex; flex-wrap: wrap; gap: 6px; }
    .truncate { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace; font-size: .82rem; }
    .notice { min-height: 22px; color: var(--muted); }
    .notice.error { color: var(--danger); }
    .notice.ok { color: var(--ok); }
    @media (max-width: 900px) {
      main { padding: 16px; }
      header { align-items: flex-start; flex-direction: column; }
      .grid { grid-template-columns: 1fr; }
      .token-row { grid-template-columns: 1fr; }
      table { min-width: 780px; }
      .table-wrap { overflow-x: auto; }
    }
    @media (prefers-color-scheme: dark) {
      :root {
        --bg: #0b1220;
        --fg: #e5e7eb;
        --muted: #9ca3af;
        --panel: #111827;
        --border: #374151;
        --accent: #3b82f6;
        --accent-strong: #2563eb;
        --danger: #f87171;
        --ok: #34d399;
        --warn: #fbbf24;
        --code: #e5e7eb;
        --codebg: #1f2937;
      }
    }
  </style>
</head>
<body>
<main>
  <header>
    <div>
      <h1>Memosima Admin</h1>
      <div class="muted">Sidecar 调试面板</div>
    </div>
    <div id="globalNotice" class="notice"></div>
  </header>

  <div class="grid">
    <section class="stack">
      <div class="panel">
        <h2>连接</h2>
        <div class="token-row">
          <div>
            <label for="tokenInput">Admin Token</label>
            <input id="tokenInput" type="password" autocomplete="off">
          </div>
          <button id="saveTokenButton" class="primary" type="button">保存</button>
          <button id="clearTokenButton" type="button">清除</button>
        </div>
      </div>

      <div class="panel">
        <h2>健康状态</h2>
        <div class="toolbar">
          <button id="refreshHealthButton" type="button">刷新</button>
        </div>
        <pre id="healthOutput">未加载</pre>
      </div>

      <div class="panel">
        <h2>详情</h2>
        <pre id="detailOutput">选择任务或标签查看详情</pre>
      </div>

      <div class="panel">
        <h2>默认提示词</h2>
        <div class="toolbar">
          <button id="refreshPromptsButton" type="button">刷新</button>
          <button id="savePromptsButton" class="primary" type="button">保存默认</button>
        </div>
        <label for="promptSystem">System</label>
        <textarea id="promptSystem" class="prompt" spellcheck="false"></textarea>
        <label for="promptUser" style="margin-top: 10px;">User</label>
        <textarea id="promptUser" class="prompt" spellcheck="false"></textarea>
        <div class="muted">可用占位符：{active_tags}、{local_plan_json}、{content}</div>
      </div>
    </section>

    <section class="stack">
      <div class="panel">
        <h2>任务</h2>
        <div class="toolbar">
          <div class="field">
            <label for="jobStatus">状态</label>
            <select id="jobStatus">
              <option value="">全部</option>
              <option value="pending">pending</option>
              <option value="running">running</option>
              <option value="succeeded">succeeded</option>
              <option value="failed">failed</option>
              <option value="waiting_user">waiting_user</option>
            </select>
          </div>
          <div class="field">
            <label for="jobLimit">数量</label>
            <input id="jobLimit" type="number" min="1" max="500" value="100">
          </div>
          <button id="refreshJobsButton" class="primary" type="button">刷新任务</button>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th style="width: 72px;">ID</th>
                <th style="width: 120px;">状态</th>
                <th style="width: 130px;">类型</th>
                <th>Key</th>
                <th style="width: 160px;">更新时间</th>
                <th style="width: 190px;">操作</th>
              </tr>
            </thead>
            <tbody id="jobsBody"></tbody>
          </table>
        </div>
      </div>

      <div class="panel">
        <h2>候选标签</h2>
        <div class="toolbar">
          <div class="field">
            <label for="candidateStatus">状态</label>
            <select id="candidateStatus">
              <option value="candidate">candidate</option>
              <option value="">全部</option>
              <option value="approved">approved</option>
              <option value="rejected">rejected</option>
            </select>
          </div>
          <div class="field">
            <label for="candidateLimit">数量</label>
            <input id="candidateLimit" type="number" min="1" max="500" value="100">
          </div>
          <button id="refreshCandidatesButton" class="primary" type="button">刷新标签</button>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th style="width: 72px;">ID</th>
                <th>Path</th>
                <th style="width: 120px;">状态</th>
                <th style="width: 90px;">置信度</th>
                <th>来源</th>
                <th style="width: 220px;">操作</th>
              </tr>
            </thead>
            <tbody id="candidatesBody"></tbody>
          </table>
        </div>
      </div>
    </section>
  </div>
</main>

<dialog id="promptDialog">
  <form method="dialog">
    <h2>临时提示词</h2>
    <label for="overrideSystem">System</label>
    <textarea id="overrideSystem" class="prompt" spellcheck="false"></textarea>
    <label for="overrideUser" style="margin-top: 10px;">User</label>
    <textarea id="overrideUser" class="prompt" spellcheck="false"></textarea>
    <div class="muted">该提示词只用于本次重试，不会保存为默认值。</div>
    <div class="actions" style="justify-content: flex-end; margin-top: 14px;">
      <button type="submit" value="cancel">取消</button>
      <button class="primary" type="submit" value="confirm">使用本次</button>
    </div>
  </form>
</dialog>

<script>
const storageKey = "memosima.adminToken";
const tokenInput = document.getElementById("tokenInput");
const globalNotice = document.getElementById("globalNotice");
const detailOutput = document.getElementById("detailOutput");
const healthOutput = document.getElementById("healthOutput");
const jobsBody = document.getElementById("jobsBody");
const candidatesBody = document.getElementById("candidatesBody");
const promptSystem = document.getElementById("promptSystem");
const promptUser = document.getElementById("promptUser");
const promptDialog = document.getElementById("promptDialog");
const overrideSystem = document.getElementById("overrideSystem");
const overrideUser = document.getElementById("overrideUser");
let promptDialogResolve = null;

function setNotice(message, kind = "") {
  globalNotice.textContent = message;
  globalNotice.className = `notice ${kind}`.trim();
}

function token() {
  return tokenInput.value.trim();
}

function showDetail(value) {
  detailOutput.textContent = JSON.stringify(value, null, 2);
}

async function requestJson(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (options.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (path.startsWith("/admin/") && path !== "/admin/ui") {
    const adminToken = token();
    if (!adminToken) {
      throw new Error("缺少 Admin Token");
    }
    headers.set("Authorization", `Bearer ${adminToken}`);
  }
  const response = await fetch(path, { ...options, headers });
  const text = await response.text();
  let data = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }
  }
  if (!response.ok) {
    const detail = data && typeof data === "object" && data.detail ? data.detail : response.statusText;
    throw new Error(`${response.status} ${detail}`);
  }
  return data;
}

function cell(text, className = "") {
  const td = document.createElement("td");
  td.textContent = text == null ? "" : String(text);
  if (className) td.className = className;
  return td;
}

function button(text, className, onClick) {
  const item = document.createElement("button");
  item.type = "button";
  item.textContent = text;
  item.className = className;
  item.addEventListener("click", onClick);
  return item;
}

async function loadHealth() {
  try {
    const data = await requestJson("/health");
    healthOutput.textContent = JSON.stringify(data, null, 2);
    setNotice("健康状态已刷新", "ok");
  } catch (error) {
    healthOutput.textContent = String(error.message || error);
    setNotice("健康状态刷新失败", "error");
  }
}

async function loadJobs() {
  try {
    const status = document.getElementById("jobStatus").value;
    const limit = document.getElementById("jobLimit").value || "100";
    const query = new URLSearchParams({ limit });
    if (status) query.set("status", status);
    const data = await requestJson(`/admin/jobs?${query.toString()}`);
    jobsBody.replaceChildren(...data.jobs.map(renderJobRow));
    setNotice(`任务已刷新：${data.jobs.length} 条`, "ok");
  } catch (error) {
    jobsBody.replaceChildren();
    setNotice(String(error.message || error), "error");
  }
}

async function loadPrompts() {
  try {
    const data = await requestJson("/admin/prompts");
    promptSystem.value = data.organize_memo.system;
    promptUser.value = data.organize_memo.user;
    setNotice("默认提示词已刷新", "ok");
    return data.organize_memo;
  } catch (error) {
    setNotice(String(error.message || error), "error");
    return null;
  }
}

async function savePrompts() {
  try {
    const data = await requestJson("/admin/prompts/organize-memo", {
      method: "PUT",
      body: JSON.stringify({ system: promptSystem.value, user: promptUser.value })
    });
    promptSystem.value = data.system;
    promptUser.value = data.user;
    setNotice("默认提示词已保存", "ok");
  } catch (error) {
    setNotice(String(error.message || error), "error");
  }
}

function renderJobRow(job) {
  const tr = document.createElement("tr");
  tr.append(
    cell(job.id, "mono"),
    cell(job.status, `status ${job.status}`),
    cell(job.type),
    cell(job.idempotency_key, "truncate mono"),
    cell(job.updated_at, "mono")
  );
  const actions = document.createElement("td");
  actions.className = "actions";
  actions.append(button("详情", "", () => showDetail(job)));
  if (job.status === "failed" || job.status === "waiting_user") {
    actions.append(button("重试", "primary", () => retryJob(job)));
  }
  tr.append(actions);
  return tr;
}

async function retryJob(job) {
  try {
    let payload = null;
    if (window.confirm("是否临时修改本次重试使用的提示词？")) {
      const prompt = await loadPrompts();
      if (!prompt) return;
      const override = await openPromptDialog(prompt);
      if (!override) return;
      payload = { prompt_override: override };
    }
    const data = await requestJson(`/admin/jobs/${job.id}/retry`, {
      method: "POST",
      body: payload ? JSON.stringify(payload) : null
    });
    showDetail(data);
    await loadJobs();
  } catch (error) {
    setNotice(String(error.message || error), "error");
  }
}

function openPromptDialog(prompt) {
  overrideSystem.value = prompt.system;
  overrideUser.value = prompt.user;
  promptDialog.returnValue = "";
  promptDialog.showModal();
  return new Promise((resolve) => {
    promptDialogResolve = resolve;
  });
}

promptDialog.addEventListener("close", () => {
  if (!promptDialogResolve) return;
  if (promptDialog.returnValue === "confirm") {
    promptDialogResolve({ system: overrideSystem.value, user: overrideUser.value });
  } else {
    promptDialogResolve(null);
  }
  promptDialogResolve = null;
});

async function loadCandidates() {
  try {
    const status = document.getElementById("candidateStatus").value;
    const limit = document.getElementById("candidateLimit").value || "100";
    const query = new URLSearchParams({ limit });
    if (status) query.set("status", status);
    const data = await requestJson(`/admin/tag-candidates?${query.toString()}`);
    candidatesBody.replaceChildren(...data.candidates.map(renderCandidateRow));
    setNotice(`候选标签已刷新：${data.candidates.length} 条`, "ok");
  } catch (error) {
    candidatesBody.replaceChildren();
    setNotice(String(error.message || error), "error");
  }
}

function renderCandidateRow(candidate) {
  const tr = document.createElement("tr");
  tr.append(
    cell(candidate.id, "mono"),
    cell(candidate.path, "mono"),
    cell(candidate.status, `status ${candidate.status}`),
    cell(candidate.confidence.toFixed(2), "mono"),
    cell(candidate.source_memo_uid || "")
  );
  const actions = document.createElement("td");
  actions.className = "actions";
  actions.append(button("详情", "", () => showDetail(candidate)));
  if (candidate.status === "candidate") {
    actions.append(button("通过", "primary", () => reviewCandidate(candidate.id, "approve")));
    actions.append(button("拒绝", "danger", () => reviewCandidate(candidate.id, "reject")));
  }
  tr.append(actions);
  return tr;
}

async function reviewCandidate(id, action) {
  const note = window.prompt("审核备注", "");
  if (note === null) return;
  try {
    const data = await requestJson(`/admin/tag-candidates/${id}/${action}`, {
      method: "POST",
      body: JSON.stringify({ note })
    });
    showDetail(data);
    await loadCandidates();
  } catch (error) {
    setNotice(String(error.message || error), "error");
  }
}

document.getElementById("saveTokenButton").addEventListener("click", () => {
  localStorage.setItem(storageKey, token());
  setNotice("Token 已保存到本机浏览器", "ok");
});
document.getElementById("clearTokenButton").addEventListener("click", () => {
  localStorage.removeItem(storageKey);
  tokenInput.value = "";
  setNotice("Token 已清除", "ok");
});
document.getElementById("refreshHealthButton").addEventListener("click", loadHealth);
document.getElementById("refreshJobsButton").addEventListener("click", loadJobs);
document.getElementById("refreshCandidatesButton").addEventListener("click", loadCandidates);
document.getElementById("refreshPromptsButton").addEventListener("click", loadPrompts);
document.getElementById("savePromptsButton").addEventListener("click", savePrompts);

tokenInput.value = localStorage.getItem(storageKey) || "";
loadHealth();
if (token()) {
  loadJobs();
  loadCandidates();
  loadPrompts();
}
</script>
</body>
</html>
"""
