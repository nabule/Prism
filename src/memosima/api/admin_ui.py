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
    .shell { max-width: 1440px; margin: 0 auto; padding: 20px; }
    .topbar { display: grid; grid-template-columns: minmax(220px, 1fr) minmax(360px, 620px); gap: 16px; align-items: start; margin-bottom: 16px; }
    h1 { margin: 0; font-size: 1.45rem; line-height: 1.2; }
    h2 { margin: 0 0 14px; font-size: 1rem; line-height: 1.2; }
    h3 { margin: 0 0 10px; font-size: .92rem; line-height: 1.2; }
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
    .tabs { display: flex; gap: 6px; overflow-x: auto; margin: 16px 0; padding-bottom: 2px; scrollbar-width: thin; }
    .tab { min-height: 36px; border-radius: 8px; }
    .tab.active { background: var(--accent); border-color: var(--accent); color: #fff; }
    .tab-panel { display: none; }
    .tab-panel.active { display: block; }
    .workspace { display: grid; grid-template-columns: minmax(0, 1fr) 360px; gap: 16px; align-items: start; }
    .overview-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; align-items: start; }
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
    .table-wrap { max-width: 100%; overflow-x: auto; }
    @media (max-width: 1099px) {
      .topbar, .workspace, .overview-grid, .grid { grid-template-columns: 1fr; }
      .token-row { grid-template-columns: 1fr; }
      table { min-width: 780px; }
    }
    @media (max-width: 700px) {
      main, .shell { padding: 12px; }
      .panel { padding: 12px; }
      .toolbar, .actions { align-items: stretch; }
      .field { flex-basis: 100%; min-width: 0; }
      button { min-height: 36px; }
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
<main class="shell">
  <header class="topbar">
    <div>
      <h1>Memosima Admin</h1>
      <div class="muted">Sidecar 管理配置</div>
    </div>
    <div id="connection" class="panel">
      <div class="token-row">
        <div>
          <label for="tokenInput">Admin Token</label>
          <input id="tokenInput" type="password" autocomplete="off">
        </div>
        <button id="saveTokenButton" class="primary" type="button">保存</button>
        <button id="clearTokenButton" type="button">清除</button>
      </div>
      <div id="globalNotice" class="notice"></div>
    </div>
  </header>

  <nav class="tabs" role="tablist" aria-label="管理功能">
    <button class="tab active" type="button" role="tab" aria-selected="true" data-tab-target="overview">概览</button>
    <button class="tab" type="button" role="tab" aria-selected="false" data-tab-target="jobs">任务</button>
    <button class="tab" type="button" role="tab" aria-selected="false" data-tab-target="tags">标签</button>
    <button class="tab" type="button" role="tab" aria-selected="false" data-tab-target="prompts">AI 配置</button>
    <button class="tab" type="button" role="tab" aria-selected="false" data-tab-target="models">模型</button>
    <button class="tab" type="button" role="tab" aria-selected="false" data-tab-target="reminders">提醒</button>
    <button class="tab" type="button" role="tab" aria-selected="false" data-tab-target="backup">备份</button>
  </nav>

  <section class="tab-panel active" data-panel="overview">
    <div class="overview-grid">
      <div class="panel">
        <h2>健康状态</h2>
        <div class="toolbar">
          <button id="refreshHealthButton" type="button">刷新</button>
        </div>
        <pre id="healthOutput">未加载</pre>
      </div>

      <div class="panel">
        <h2>常用入口</h2>
        <div class="toolbar">
          <button type="button" data-tab-target="jobs">查看任务</button>
          <button type="button" data-tab-target="tags">标签处理</button>
          <button type="button" data-tab-target="models">模型配置</button>
          <button type="button" data-tab-target="backup">备份恢复</button>
        </div>
        <div class="muted">使用上方标签聚合任务、标签、AI 配置、模型、提醒和备份能力。</div>
      </div>

      <div class="panel">
        <h2>备份快捷入口</h2>
        <div class="toolbar">
          <button id="downloadBackupButton" class="primary" type="button">下载备份</button>
          <button type="button" data-tab-target="backup">恢复数据</button>
        </div>
        <div class="muted">备份 ZIP 不包含真实密钥；恢复操作在「备份」标签中完成。</div>
      </div>
    </div>
  </section>

  <section class="tab-panel" data-panel="jobs">
    <div class="workspace">
      <div id="jobs" class="panel">
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
      <aside class="panel">
        <h2>详情</h2>
        <pre id="detailOutput">选择任务或标签查看详情</pre>
      </aside>
    </div>
  </section>

  <section class="tab-panel" data-panel="tags">
    <div class="workspace">
      <div class="stack">
        <div id="tag-summary" class="panel">
          <h2>标签总结</h2>
          <div class="toolbar">
            <div class="field">
              <label for="tagSummaryTag">标签</label>
              <input id="tagSummaryTag" value="#项目/个人AI知识库">
            </div>
            <div class="field">
              <label for="tagSummaryLimit">数量</label>
              <input id="tagSummaryLimit" type="number" min="1" max="200" value="50">
            </div>
            <button id="createTagSummaryButton" class="primary" type="button">生成总结</button>
          </div>
          <pre id="tagSummaryOutput">未生成</pre>
        </div>

        <div id="tag-candidates" class="panel">
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
      </div>
      <aside class="panel">
        <h2>详情</h2>
        <pre id="tagDetailMirror">详情会显示在任务页的共享详情区域</pre>
      </aside>
    </div>
  </section>

  <section class="tab-panel" data-panel="prompts">
    <div class="panel">
      <h2>AI 调用配置</h2>
      <div class="toolbar">
        <button id="refreshPromptsButton" type="button">刷新</button>
        <button id="savePromptsButton" class="primary" type="button">保存 AI 配置</button>
      </div>
      <div class="muted">每个 AI 调用点都可以单独选择大模型配置；留空时使用 <span class="mono">config/models.yaml</span> 的默认 provider。</div>

      <label for="promptProvider" style="margin-top: 14px;">单条 memo 整理使用的模型配置</label>
      <select id="promptProvider"></select>
      <label for="promptSystem" style="margin-top: 10px;">单条 memo 整理 System 提示词</label>
      <textarea id="promptSystem" class="prompt" spellcheck="false"></textarea>
      <label for="promptUser" style="margin-top: 10px;">单条 memo 整理 User 提示词</label>
      <textarea id="promptUser" class="prompt" spellcheck="false"></textarea>
      <div class="muted">用于新 memo 的结构化整理、标题、摘要、待办和标签建议。可用占位符：{active_tags}、{local_plan_json}、{content}</div>

      <label for="tagSummaryProvider" style="margin-top: 14px;">标签总结使用的模型配置</label>
      <select id="tagSummaryProvider"></select>
      <label for="tagSummarySystem" style="margin-top: 10px;">标签总结 System 提示词</label>
      <textarea id="tagSummarySystem" class="prompt" spellcheck="false"></textarea>
      <label for="tagSummaryUser" style="margin-top: 10px;">标签总结 User 提示词</label>
      <textarea id="tagSummaryUser" class="prompt" spellcheck="false"></textarea>
      <div class="muted">用于按标签汇总多条 memo 并生成 Markdown 总结。可用占位符：{tag}、{memo_count}、{memos_markdown}</div>

      <label for="reminderProvider" style="margin-top: 14px;">提醒抽取使用的模型配置</label>
      <select id="reminderProvider"></select>
      <label for="reminderSystem" style="margin-top: 10px;">提醒抽取 System 提示词</label>
      <textarea id="reminderSystem" class="prompt" spellcheck="false"></textarea>
      <label for="reminderUser" style="margin-top: 10px;">提醒抽取 User 提示词</label>
      <textarea id="reminderUser" class="prompt" spellcheck="false"></textarea>
      <div class="muted">用于识别带触发标签的提醒时间，只处理明确提醒请求。可用占位符：{trigger_tag}、{now}、{timezone}、{content}</div>
    </div>
  </section>

  <section class="tab-panel" data-panel="models">
    <div id="models" class="panel">
      <h2>大模型</h2>
      <div class="toolbar">
        <button id="refreshModelsButton" type="button">刷新</button>
        <button id="saveModelsButton" class="primary" type="button">保存配置</button>
      </div>
      <label for="modelProviderSelect">Provider</label>
      <select id="modelProviderSelect"></select>
      <label for="modelBaseUrl" style="margin-top: 10px;">Base URL</label>
      <input id="modelBaseUrl" autocomplete="off">
      <label for="modelName" style="margin-top: 10px;">模型名</label>
      <input id="modelName" autocomplete="off">
      <label for="modelApiKeyEnv" style="margin-top: 10px;">Key 环境变量</label>
      <input id="modelApiKeyEnv" autocomplete="off">
      <label for="modelApiKey" style="margin-top: 10px;">API Key</label>
      <input id="modelApiKey" type="password" autocomplete="off" placeholder="留空则不修改已保存 key">
      <div id="modelKeyStatus" class="muted"></div>
      <div class="toolbar" style="margin-top: 10px;">
        <div class="field">
          <label for="modelTemperature">Temperature</label>
          <input id="modelTemperature" type="number" min="0" max="2" step="0.1">
        </div>
        <div class="field">
          <label for="modelMaxTokens">Max Tokens</label>
          <input id="modelMaxTokens" type="number" min="1" max="200000" placeholder="留空">
        </div>
      </div>
      <label for="modelResponseFormat">Response Format</label>
      <input id="modelResponseFormat" autocomplete="off" placeholder="json_object 或留空">
      <label for="modelExtraBody" style="margin-top: 10px;">Extra Body JSON</label>
      <textarea id="modelExtraBody" spellcheck="false">{}</textarea>
      <div class="muted">保存后会更新 <span class="mono">config/models.yaml</span>；key 写入 <span class="mono">config/.env.local</span>，不会写入备份或模型配置文件。</div>
    </div>
  </section>

  <section class="tab-panel" data-panel="reminders">
    <div class="workspace">
      <div class="panel">
        <h2>提醒</h2>
        <div class="toolbar">
          <div class="field">
            <label for="reminderStatus">状态</label>
            <select id="reminderStatus">
              <option value="">全部</option>
              <option value="pending">pending</option>
              <option value="failed">failed</option>
              <option value="sent">sent</option>
              <option value="cancelled">cancelled</option>
            </select>
          </div>
          <div class="field">
            <label for="reminderLimit">数量</label>
            <input id="reminderLimit" type="number" min="1" max="500" value="100">
          </div>
          <button id="refreshRemindersButton" class="primary" type="button">刷新提醒</button>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th style="width: 72px;">ID</th>
                <th>标题</th>
                <th style="width: 120px;">状态</th>
                <th style="width: 180px;">到期</th>
                <th style="width: 130px;">来源</th>
                <th style="width: 190px;">操作</th>
              </tr>
            </thead>
            <tbody id="remindersBody"></tbody>
          </table>
        </div>
      </div>
      <aside class="panel">
        <h2>详情</h2>
        <pre id="reminderDetailMirror">详情会显示在任务页的共享详情区域</pre>
      </aside>
    </div>
  </section>

  <section class="tab-panel" data-panel="backup">
    <div id="backup" class="panel">
      <h2>备份恢复</h2>
      <div class="toolbar">
        <button id="downloadBackupButtonMirror" class="primary" type="button">下载备份</button>
      </div>
      <label for="restoreBackupInput">恢复 Sidecar 数据库</label>
      <input id="restoreBackupInput" type="file" accept=".zip,application/zip">
      <div class="toolbar" style="margin-top: 10px;">
        <button id="restoreBackupButton" class="danger" type="button">上传恢复</button>
      </div>
      <div class="muted">备份包含 Sidecar SQLite 和非机密配置文件；恢复只替换 Sidecar SQLite，不自动覆盖配置。</div>
    </div>
  </section>
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
const remindersBody = document.getElementById("remindersBody");
const promptProvider = document.getElementById("promptProvider");
const promptSystem = document.getElementById("promptSystem");
const promptUser = document.getElementById("promptUser");
const tagSummaryProvider = document.getElementById("tagSummaryProvider");
const tagSummarySystem = document.getElementById("tagSummarySystem");
const tagSummaryUser = document.getElementById("tagSummaryUser");
const reminderProvider = document.getElementById("reminderProvider");
const reminderSystem = document.getElementById("reminderSystem");
const reminderUser = document.getElementById("reminderUser");
const tagSummaryOutput = document.getElementById("tagSummaryOutput");
const modelProviderSelect = document.getElementById("modelProviderSelect");
const modelBaseUrl = document.getElementById("modelBaseUrl");
const modelName = document.getElementById("modelName");
const modelApiKeyEnv = document.getElementById("modelApiKeyEnv");
const modelApiKey = document.getElementById("modelApiKey");
const modelKeyStatus = document.getElementById("modelKeyStatus");
const modelTemperature = document.getElementById("modelTemperature");
const modelMaxTokens = document.getElementById("modelMaxTokens");
const modelResponseFormat = document.getElementById("modelResponseFormat");
const modelExtraBody = document.getElementById("modelExtraBody");
const promptDialog = document.getElementById("promptDialog");
const overrideSystem = document.getElementById("overrideSystem");
const overrideUser = document.getElementById("overrideUser");
const tabButtons = Array.from(document.querySelectorAll(".tabs [data-tab-target]"));
const panelTriggers = Array.from(document.querySelectorAll("[data-tab-target]"));
const panels = Array.from(document.querySelectorAll("[data-panel]"));
let promptDialogResolve = null;
let modelProviders = [];
let promptConfig = null;
const hashPanelMap = {
  overview: { panel: "overview" },
  jobs: { panel: "jobs" },
  tags: { panel: "tags" },
  "tag-candidates": { panel: "tags", focus: "tag-candidates" },
  "tag-summary": { panel: "tags", focus: "tag-summary" },
  prompts: { panel: "prompts" },
  models: { panel: "models" },
  reminders: { panel: "reminders" },
  backup: { panel: "backup" }
};

function setNotice(message, kind = "") {
  globalNotice.textContent = message;
  globalNotice.className = `notice ${kind}`.trim();
}

function token() {
  return tokenInput.value.trim();
}

function showDetail(value) {
  const text = JSON.stringify(value, null, 2);
  detailOutput.textContent = text;
  const tagMirror = document.getElementById("tagDetailMirror");
  const reminderMirror = document.getElementById("reminderDetailMirror");
  if (tagMirror) tagMirror.textContent = text;
  if (reminderMirror) reminderMirror.textContent = text;
}

function activatePanel(panelName, options = {}) {
  const nextPanel = panels.find((panel) => panel.dataset.panel === panelName) || panels[0];
  if (!nextPanel) return;
  const nextName = nextPanel.dataset.panel;
  for (const panel of panels) {
    panel.classList.toggle("active", panel === nextPanel);
  }
  for (const tab of tabButtons) {
    const isActive = tab.dataset.tabTarget === nextName;
    tab.classList.toggle("active", isActive);
    if (tab.getAttribute("role") === "tab") {
      tab.setAttribute("aria-selected", isActive ? "true" : "false");
    }
  }
  if (options.focus) {
    const target = document.getElementById(options.focus);
    if (target) {
      setTimeout(() => target.scrollIntoView({ behavior: "smooth", block: "start" }), 0);
    }
  }
}

function showPanelFromHash() {
  const targetId = decodeURIComponent(window.location.hash || "").replace(/^#/, "") || "overview";
  const target = hashPanelMap[targetId] || hashPanelMap.overview;
  activatePanel(target.panel, { focus: target.focus });
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

function adminHeaders() {
  const adminToken = token();
  if (!adminToken) {
    throw new Error("缺少 Admin Token");
  }
  return { Authorization: `Bearer ${adminToken}` };
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
    promptConfig = data;
    renderPromptProviderSelects();
    promptSystem.value = data.organize_memo.system;
    promptUser.value = data.organize_memo.user;
    tagSummarySystem.value = data.tag_summary.system;
    tagSummaryUser.value = data.tag_summary.user;
    reminderSystem.value = data.reminder_extraction.system;
    reminderUser.value = data.reminder_extraction.user;
    setNotice("AI 调用配置已刷新", "ok");
    return data.organize_memo;
  } catch (error) {
    setNotice(String(error.message || error), "error");
    return null;
  }
}

async function loadModels() {
  try {
    const data = await requestJson("/admin/models");
    modelProviders = data.providers || [];
    modelProviderSelect.replaceChildren(...modelProviders.map((provider) => {
      const option = document.createElement("option");
      option.value = provider.name;
      option.textContent = provider.is_default ? `${provider.name}（默认）` : provider.name;
      return option;
    }));
    modelProviderSelect.value = data.default_provider;
    renderSelectedModelProvider();
    renderPromptProviderSelects();
    setNotice("大模型配置已刷新", "ok");
  } catch (error) {
    setNotice(String(error.message || error), "error");
  }
}

function renderSelectedModelProvider() {
  const provider = modelProviders.find((item) => item.name === modelProviderSelect.value) || modelProviders[0];
  if (!provider) return;
  modelProviderSelect.value = provider.name;
  modelBaseUrl.value = provider.base_url || "";
  modelName.value = provider.default_model || "";
  modelApiKeyEnv.value = provider.api_key_env || "";
  modelApiKey.value = "";
  modelKeyStatus.textContent = provider.api_key_present ? "Key 已配置" : "Key 未配置";
  modelTemperature.value = provider.temperature ?? 0.2;
  modelMaxTokens.value = provider.max_tokens == null ? "" : provider.max_tokens;
  modelResponseFormat.value = provider.response_format || "";
  modelExtraBody.value = JSON.stringify(provider.extra_body || {}, null, 2);
}

function renderPromptProviderSelects() {
  const selects = [
    [promptProvider, promptConfig?.organize_memo?.provider || ""],
    [tagSummaryProvider, promptConfig?.tag_summary?.provider || ""],
    [reminderProvider, promptConfig?.reminder_extraction?.provider || ""]
  ];
  for (const [select, value] of selects) {
    if (!select) continue;
    const options = [promptProviderOption("", "使用默认 provider")];
    for (const provider of modelProviders) {
      options.push(promptProviderOption(provider.name, provider.is_default ? `${provider.name}（当前默认）` : provider.name));
    }
    select.replaceChildren(...options);
    select.value = value;
  }
}

function promptProviderOption(value, text) {
  const option = document.createElement("option");
  option.value = value;
  option.textContent = text;
  return option;
}

async function saveModels() {
  try {
    let extraBody = {};
    const extraText = modelExtraBody.value.trim();
    if (extraText) {
      extraBody = JSON.parse(extraText);
      if (!extraBody || Array.isArray(extraBody) || typeof extraBody !== "object") {
        throw new Error("Extra Body 必须是 JSON 对象");
      }
    }
    const payload = {
      default_provider: modelProviderSelect.value,
      base_url: modelBaseUrl.value,
      api_key_env: modelApiKeyEnv.value,
      default_model: modelName.value,
      temperature: Number(modelTemperature.value || "0.2"),
      max_tokens: modelMaxTokens.value ? Number(modelMaxTokens.value) : null,
      response_format: modelResponseFormat.value || null,
      extra_body: extraBody
    };
    if (modelApiKey.value.trim()) {
      payload.api_key = modelApiKey.value.trim();
    }
    const data = await requestJson("/admin/models", {
      method: "PUT",
      body: JSON.stringify(payload)
    });
    modelProviders = data.providers || [];
    modelProviderSelect.replaceChildren(...modelProviders.map((provider) => {
      const option = document.createElement("option");
      option.value = provider.name;
      option.textContent = provider.is_default ? `${provider.name}（默认）` : provider.name;
      return option;
    }));
    modelProviderSelect.value = data.default_provider;
    renderSelectedModelProvider();
    await loadHealth();
    setNotice("大模型配置已保存", "ok");
  } catch (error) {
    setNotice(String(error.message || error), "error");
  }
}

async function savePrompts() {
  try {
    const data = await requestJson("/admin/prompts/organize-memo", {
      method: "PUT",
      body: JSON.stringify({ provider: promptProvider.value || null, system: promptSystem.value, user: promptUser.value })
    });
    const tagData = await requestJson("/admin/prompts/tag-summary", {
      method: "PUT",
      body: JSON.stringify({ provider: tagSummaryProvider.value || null, system: tagSummarySystem.value, user: tagSummaryUser.value })
    });
    const reminderData = await requestJson("/admin/prompts/reminder-extraction", {
      method: "PUT",
      body: JSON.stringify({ provider: reminderProvider.value || null, system: reminderSystem.value, user: reminderUser.value })
    });
    promptConfig = { organize_memo: data, tag_summary: tagData, reminder_extraction: reminderData };
    renderPromptProviderSelects();
    promptSystem.value = data.system;
    promptUser.value = data.user;
    tagSummarySystem.value = tagData.system;
    tagSummaryUser.value = tagData.user;
    reminderSystem.value = reminderData.system;
    reminderUser.value = reminderData.user;
    setNotice("AI 调用配置已保存", "ok");
  } catch (error) {
    setNotice(String(error.message || error), "error");
  }
}

async function createTagSummary() {
  try {
    const tag = document.getElementById("tagSummaryTag").value.trim();
    const limit = Number(document.getElementById("tagSummaryLimit").value || "50");
    const data = await requestJson("/admin/tag-summaries", {
      method: "POST",
      body: JSON.stringify({ tag, limit })
    });
    tagSummaryOutput.textContent = JSON.stringify(data, null, 2);
    showDetail(data);
    setNotice(`标签总结已生成：memos/${data.summary_memo_uid}`, "ok");
  } catch (error) {
    tagSummaryOutput.textContent = String(error.message || error);
    setNotice(String(error.message || error), "error");
  }
}

async function downloadBackup() {
  try {
    const response = await fetch("/admin/backups/download", { headers: adminHeaders() });
    if (!response.ok) {
      throw new Error(`${response.status} ${response.statusText}`);
    }
    const blob = await response.blob();
    const disposition = response.headers.get("Content-Disposition") || "";
    const match = disposition.match(/filename="([^"]+)"/);
    const filename = match ? match[1] : "memosima-sidecar-backup.zip";
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    setNotice("备份已开始下载", "ok");
  } catch (error) {
    setNotice(String(error.message || error), "error");
  }
}

async function restoreBackup() {
  const input = document.getElementById("restoreBackupInput");
  const file = input.files && input.files[0];
  if (!file) {
    setNotice("请选择备份 ZIP 文件", "error");
    return;
  }
  if (!window.confirm("恢复会替换当前 Sidecar SQLite 数据库，继续？")) {
    return;
  }
  try {
    const response = await fetch("/admin/backups/restore", {
      method: "POST",
      headers: { ...adminHeaders(), "Content-Type": "application/zip" },
      body: await file.arrayBuffer()
    });
    const data = await response.json();
    if (!response.ok) {
      const detail = data && data.detail ? data.detail : response.statusText;
      throw new Error(`${response.status} ${detail}`);
    }
    showDetail(data);
    setNotice("备份已恢复", "ok");
    await Promise.all([loadJobs(), loadCandidates(), loadReminders(), loadHealth()]);
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

async function loadReminders() {
  try {
    const status = document.getElementById("reminderStatus").value;
    const limit = document.getElementById("reminderLimit").value || "100";
    const query = new URLSearchParams({ limit });
    if (status) query.set("status", status);
    const data = await requestJson(`/admin/reminders?${query.toString()}`);
    remindersBody.replaceChildren(...data.reminders.map(renderReminderRow));
    setNotice(`提醒已刷新：${data.reminders.length} 条`, "ok");
  } catch (error) {
    remindersBody.replaceChildren();
    setNotice(String(error.message || error), "error");
  }
}

function renderReminderRow(reminder) {
  const tr = document.createElement("tr");
  tr.append(
    cell(reminder.id, "mono"),
    cell(reminder.title),
    cell(reminder.status, `status ${reminder.status}`),
    cell(reminder.due_at, "mono"),
    cell(reminder.source_memo_uid, "mono")
  );
  const actions = document.createElement("td");
  actions.className = "actions";
  actions.append(button("详情", "", () => showDetail(reminder)));
  if (reminder.status === "failed" || reminder.status === "sent") {
    actions.append(button("重试", "primary", () => updateReminder(reminder.id, "retry")));
  }
  if (reminder.status === "pending" || reminder.status === "failed") {
    actions.append(button("取消", "danger", () => updateReminder(reminder.id, "cancel")));
  }
  tr.append(actions);
  return tr;
}

async function updateReminder(id, action) {
  try {
    const data = await requestJson(`/admin/reminders/${id}/${action}`, { method: "POST" });
    showDetail(data);
    await loadReminders();
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
document.getElementById("refreshRemindersButton").addEventListener("click", loadReminders);
document.getElementById("refreshPromptsButton").addEventListener("click", loadPrompts);
document.getElementById("savePromptsButton").addEventListener("click", savePrompts);
document.getElementById("refreshModelsButton").addEventListener("click", loadModels);
document.getElementById("saveModelsButton").addEventListener("click", saveModels);
modelProviderSelect.addEventListener("change", renderSelectedModelProvider);
document.getElementById("createTagSummaryButton").addEventListener("click", createTagSummary);
document.getElementById("downloadBackupButton").addEventListener("click", downloadBackup);
document.getElementById("downloadBackupButtonMirror").addEventListener("click", downloadBackup);
document.getElementById("restoreBackupButton").addEventListener("click", restoreBackup);
for (const tab of panelTriggers) {
  tab.addEventListener("click", () => {
    const panelName = tab.dataset.tabTarget;
    const hash = panelName === "overview" ? "overview" : panelName;
    if (window.location.hash === `#${hash}`) {
      activatePanel(panelName);
    } else {
      window.location.hash = hash;
    }
  });
}

tokenInput.value = localStorage.getItem(storageKey) || "";
loadHealth();
if (token()) {
  loadJobs();
  loadCandidates();
  loadReminders();
  loadPrompts();
  loadModels();
}
window.addEventListener("hashchange", showPanelFromHash);
showPanelFromHash();
</script>
</body>
</html>
"""
