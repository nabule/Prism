from __future__ import annotations


ADMIN_UI_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Prism (棱镜) Admin</title>
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
    
    /* Q&A Pills and Autocomplete Styles */
    .pills-container {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      padding: 6px;
      border: 1px solid var(--border);
      border-radius: 8px;
      background: var(--panel);
      min-height: 40px;
      align-items: center;
      position: relative;
    }
    .pill {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      background: var(--codebg);
      color: var(--fg);
      padding: 2px 8px;
      border-radius: 12px;
      font-size: 0.85rem;
      border: 1px solid var(--border);
    }
    .pill .remove {
      cursor: pointer;
      color: var(--muted);
      font-weight: bold;
      font-size: 0.9rem;
      margin-left: 2px;
    }
    .pill .remove:hover {
      color: var(--danger);
    }
    .pill-input {
      border: none !important;
      outline: none !important;
      padding: 4px 6px !important;
      flex: 1;
      min-width: 120px;
      background: transparent !important;
      color: var(--fg);
    }
    .autocomplete-list {
      position: absolute;
      top: 100%;
      left: 0;
      right: 0;
      z-index: 1000;
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 8px;
      max-height: 200px;
      overflow-y: auto;
      box-shadow: 0 4px 12px rgba(0,0,0,0.15);
      margin-top: 4px;
      display: none;
    }
    .autocomplete-item {
      padding: 8px 12px;
      cursor: pointer;
    }
    .autocomplete-item:hover {
      background: var(--accent);
      color: #fff;
    }
    .prompt-container {
      position: relative;
    }
    .copy-btn-floating {
      position: absolute;
      top: 12px;
      right: 12px;
      background: var(--accent);
      color: white;
      border: none;
      padding: 6px 12px;
      border-radius: 6px;
      cursor: pointer;
      font-size: 0.8rem;
      z-index: 10;
      transition: background 0.2s, transform 0.1s;
    }
    .copy-btn-floating:hover {
      background: var(--accent-strong);
    }
    .copy-btn-floating:active {
      transform: scale(0.95);
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
      <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 4px;">
        <svg class="prism-logo" viewBox="0 0 100 100" width="34" height="34" style="vertical-align: middle; flex-shrink: 0;">
          <defs>
            <linearGradient id="rainbow" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stop-color="#ff4b4b" />
              <stop offset="20%" stop-color="#ff8533" />
              <stop offset="40%" stop-color="#ffdd33" />
              <stop offset="60%" stop-color="#33cc66" />
              <stop offset="80%" stop-color="#3399ff" />
              <stop offset="100%" stop-color="#8033ff" />
            </linearGradient>
            <linearGradient id="glass" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stop-color="rgba(100,116,139,0.2)" />
              <stop offset="100%" stop-color="rgba(100,116,139,0.05)" />
            </linearGradient>
          </defs>
          <path d="M 0 50 L 45 42" stroke="#60a5fa" stroke-width="4" stroke-linecap="round" opacity="0.9" />
          <path d="M 55 45 L 100 20 L 100 80 Z" fill="url(#rainbow)" opacity="0.8" />
          <polygon points="50,15 20,75 80,75" fill="url(#glass)" stroke="#94a3b8" stroke-width="2.5" />
          <path d="M 45 42 L 55 45" stroke="#93c5fd" stroke-width="2.5" opacity="0.85" />
        </svg>
        <h1 style="margin: 0;">Prism (棱镜) Memosima Admin</h1>
      </div>
      <div class="muted" style="display: flex; align-items: center; gap: 8px;">
        <span>Sidecar 管理配置</span>
        <span id="version-display" style="font-size: 11px; font-family: monospace; background: var(--codebg); color: var(--muted); border: 1px solid var(--border); padding: 1px 6px; border-radius: 4px;"></span>
      </div>
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
    <button class="tab" type="button" role="tab" aria-selected="false" data-tab-target="docparser">文档解析</button>
    <button class="tab" type="button" role="tab" aria-selected="false" data-tab-target="vector-search">向量库</button>
    <button class="tab" type="button" role="tab" aria-selected="false" data-tab-target="memos">Memos 同步</button>
    <button class="tab" type="button" role="tab" aria-selected="false" data-tab-target="backup">备份</button>
    <button class="tab" type="button" role="tab" aria-selected="false" data-tab-target="qa">QA 离线问答</button>
    <button class="tab" type="button" role="tab" aria-selected="false" data-tab-target="reprocess">重新整理</button>
    <button class="tab" type="button" role="tab" aria-selected="false" data-tab-target="logs">系统日志</button>
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
          <button type="button" data-tab-target="vector-search">向量库配置</button>
          <button type="button" data-tab-target="memos">Memos 同步</button>
          <button type="button" data-tab-target="backup">备份恢复</button>
          <button type="button" data-tab-target="logs">系统日志</button>
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
          <div class="toolbar-wrapper" style="margin-bottom: 12px;">
            <div class="grid" style="grid-template-columns: 1fr 120px auto; gap: 12px; align-items: end;">
              <div class="field" style="position: relative; margin-bottom: 0;">
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px;">
                  <label for="tagSummaryTagInput" style="margin-bottom: 0;">选择业务标签 (支持模糊/拼音搜索)</label>
                  <div style="display: flex; align-items: center; gap: 6px;">
                    <span style="font-size: 0.8rem; color: var(--muted);">逻辑关系：</span>
                    <select id="tagSummaryTagRelation" style="width: auto; padding: 2px 6px; font-size: 0.8rem; border-radius: 4px;">
                      <option value="OR">或 (OR)</option>
                      <option value="AND">与 (AND)</option>
                    </select>
                  </div>
                </div>
                <div class="pills-container" id="tagSummaryTagContainer">
                  <input type="text" id="tagSummaryTagInput" class="pill-input" placeholder="输入标签前缀，如 #项目..." autocomplete="off">
                  <div id="tagSummaryTagAutocomplete" class="autocomplete-list"></div>
                </div>
              </div>
              <div class="field" style="margin-bottom: 0;">
                <label for="tagSummaryLimit">最大 Memo 数量</label>
                <input id="tagSummaryLimit" type="number" min="1" max="200" value="50" style="width: 100%;">
              </div>
              <div style="margin-bottom: 0;">
                <button id="createTagSummaryButton" class="primary" type="button" style="height: 38px;">生成总结</button>
              </div>
            </div>
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
      <aside style="display: flex; flex-direction: column; gap: 16px;">
        <div class="panel">
          <h2>详情</h2>
          <pre id="reminderDetailMirror">详情会显示在任务页的共享详情区域</pre>
        </div>
        <div class="panel stack">
          <h2>提醒配置</h2>
          <div class="field" style="margin-top: 10px;">
            <label><input id="remindersEnabled" type="checkbox"> 启用时间提醒模块</label>
          </div>
          <div class="field" style="margin-top: 10px;">
            <label for="remindersTriggerTag" style="display: block; font-weight: bold; margin-bottom: 4px;">触发提醒标签</label>
            <input id="remindersTriggerTag" type="text" placeholder="例如 #提醒" style="width: 100%; box-sizing: border-box;">
          </div>
          <div class="field" style="margin-top: 10px;">
            <label for="remindersConfidence" style="display: block; font-weight: bold; margin-bottom: 4px;">置信度阈值 (0.0 - 1.0)</label>
            <input id="remindersConfidence" type="number" min="0" max="1" step="0.05" style="width: 100%; box-sizing: border-box;">
          </div>
          <div class="field" style="margin-top: 10px;">
            <label for="remindersTimeout" style="display: block; font-weight: bold; margin-bottom: 4px;">模型超时时间 (秒)</label>
            <input id="remindersTimeout" type="number" min="1" max="60" style="width: 100%; box-sizing: border-box;">
          </div>
          <div class="field" style="margin-top: 10px;">
            <label for="remindersWebhookUrl" style="display: block; font-weight: bold; margin-bottom: 4px;">提醒通知推送 Webhook URL</label>
            <input id="remindersWebhookUrl" type="password" placeholder="留空保持不变，或输入新 URL/Bark Key" style="width: 100%; box-sizing: border-box;">
            <div class="muted" style="margin-top: 4px; font-size: 11px;">例如：<code>https://api.day.app/your-bark-key/</code>。写入 <span class="mono">config/.env.local</span>。</div>
          </div>
          <div style="margin-top: 16px;">
            <button id="saveRemindersConfigButton" class="primary" style="width: 100%;">保存提醒配置</button>
          </div>
        </div>
      </aside>
    </div>
  </section>

  <section class="tab-panel" data-panel="vector-search">
      <div class="topbar">
        <div>
          <h1>系统配置</h1>
          <div class="muted">配置离线 RAG 问答及更多系统参数</div>
        </div>
      </div>
      <div class="panel stack">
          <h2>离线向量库 (Vector Search)</h2>
          <div class="field" style="margin-top: 10px;">
            <label><input id="vectorSearchEnabled" type="checkbox"> 启用离线 RAG 向量检索</label>
          </div>
          <div class="field" style="margin-top: 10px;">
            <label for="vectorSearchModel" style="display: block; font-weight: bold; margin-bottom: 4px;">Embedding 模型 (SiliconFlow 等兼容接口)</label>
            <input id="vectorSearchModel" type="text" placeholder="例如 BAAI/bge-m3" style="width: 100%; box-sizing: border-box;">
          </div>
          <div class="field" style="margin-top: 10px;">
            <label for="vectorSearchBaseUrl" style="display: block; font-weight: bold; margin-bottom: 4px;">API Base URL</label>
            <input id="vectorSearchBaseUrl" type="text" placeholder="https://api.siliconflow.cn/v1" style="width: 100%; box-sizing: border-box;">
          </div>
          <div class="field" style="margin-top: 10px;">
            <label for="vectorSearchApiKey" style="display: block; font-weight: bold; margin-bottom: 4px;">API Key</label>
            <input id="vectorSearchApiKey" type="password" placeholder="留空保持不变，输入新 Key 则覆盖保存至 .env.local" style="width: 100%; box-sizing: border-box;">
          </div>
          <div style="margin-top: 16px;">
            <button id="saveVectorSearchConfigButton" class="primary">保存向量库配置</button>
          </div>
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

    <div class="panel" style="margin-top: 20px; border-color: var(--danger);">
      <h2 style="color: var(--danger);">危险操作</h2>
      <div class="muted">重置数据库将清空所有已处理的笔记、任务日志、标签候选和向量索引。此操作不可撤格！</div>
      <div class="toolbar" style="margin-top: 10px;">
        <button id="resetDatabaseButton" class="danger" type="button">重置数据库</button>
      </div>
    </div>
  </section>

  <section class="tab-panel" data-panel="memos">
    <div id="memos-config" class="panel">
      <h2>Memos 同步配置</h2>
      <div class="toolbar">
        <button id="refreshMemosConfigButton" type="button">刷新</button>
        <button id="saveMemosConfigButton" class="primary" type="button">保存配置</button>
      </div>
      <div class="muted">配置 Memos 主站的同步地址与认证 Token。API Token 会写入安全存储 <span class="mono">config/.env.local</span> 中。</div>

      <label for="memosBaseUrl" style="margin-top: 14px;">Memos 接口 Base URL (MEMOS_BASE_URL)</label>
      <input id="memosBaseUrl" autocomplete="off" placeholder="例如 http://memos:5230 或 https://your-memos-domain">

      <label for="memosApiToken" style="margin-top: 10px;">Memos API Token (MEMOS_API_TOKEN)</label>
      <input id="memosApiToken" type="password" autocomplete="off" placeholder="留空保持不变">
      <div id="memosTokenStatus" class="muted" style="margin-top: 4px; font-size: 0.85rem;"></div>
    </div>

    <div class="panel" style="margin-top: 20px; border-color: var(--danger);">
      <h2 style="color: var(--danger);">危险操作</h2>
      <div class="muted">删除 Memos 主站中当前用户的所有笔记。此操作会物理删除 Memos 服务器上的全部笔记，并清空 Sidecar 本地数据库中的同步记录。操作不可逆，请谨慎执行！</div>
      <div class="toolbar" style="margin-top: 10px;">
        <button id="deleteAllMemosButton" class="danger" type="button">删除当前用户的所有 Memos</button>
      </div>
    </div>
  </section>

  <section class="tab-panel" data-panel="docparser">
    <div id="docparser" class="panel">
      <h2>文档解析（MinerU）</h2>
      <div class="toolbar">
        <button id="refreshDocParserButton" type="button">刷新</button>
        <button id="saveDocParserButton" class="primary" type="button">保存配置</button>
      </div>
      <div class="muted">配置 MinerU 文档解析服务，用于将 PDF / Office 等附件转为 Markdown。API Key 写入 <span class="mono">config/.env.local</span>，不会保存到配置文件或备份中。</div>

      <label for="dpProvider" style="margin-top: 14px;">Provider</label>
      <select id="dpProvider">
        <option value="mineru">mineru</option>
        <option value="disabled">disabled（关闭）</option>
      </select>

      <label for="dpBaseUrl" style="margin-top: 10px;">Base URL</label>
      <input id="dpBaseUrl" autocomplete="off" placeholder="https://mineru.net">

      <label for="dpTokenEnv" style="margin-top: 10px;">Token 环境变量名</label>
      <input id="dpTokenEnv" autocomplete="off" placeholder="MINERU_API_TOKEN">

      <label for="dpApiKey" style="margin-top: 10px;">API Key</label>
      <input id="dpApiKey" type="password" autocomplete="off" placeholder="留空则不修改已保存 key">
      <div id="dpKeyStatus" class="muted"></div>

      <label for="dpModelVersion" style="margin-top: 10px;">模型版本</label>
      <select id="dpModelVersion">
        <option value="vlm">vlm（视觉语言模型，推荐）</option>
        <option value="doclayout">doclayout（布局模型）</option>
      </select>

      <label for="dpLanguage" style="margin-top: 10px;">语言</label>
      <select id="dpLanguage">
        <option value="ch">中文 (ch)</option>
        <option value="en">英文 (en)</option>
        <option value="ja">日文 (ja)</option>
        <option value="ko">韩文 (ko)</option>
      </select>

      <div class="toolbar" style="margin-top: 14px;">
        <div class="field">
          <label for="dpTimeout">超时时间 (秒)</label>
          <input id="dpTimeout" type="number" min="1" max="600" value="60">
        </div>
        <div class="field">
          <label for="dpPollInterval">轮询间隔 (秒)</label>
          <input id="dpPollInterval" type="number" min="1" max="60" value="3">
        </div>
        <div class="field">
          <label for="dpMaxPolls">最大轮询次数</label>
          <input id="dpMaxPolls" type="number" min="1" max="600" value="60">
        </div>
      </div>

      <div class="toolbar" style="margin-top: 10px;">
        <div class="field">
          <label><input id="dpEnableTable" type="checkbox" checked> 启用表格识别</label>
        </div>
        <div class="field">
          <label><input id="dpEnableFormula" type="checkbox" checked> 启用公式识别</label>
        </div>
        <div class="field">
          <label><input id="dpIsOcr" type="checkbox"> 强制 OCR 模式</label>
        </div>
      </div>
    </div>
  </section>

  <section class="tab-panel" data-panel="qa">
    <div class="grid">
      <div class="panel stack">
        <h2>QA 离线问答 & Prompt 编译器</h2>
        <div class="field">
          <label>知识库标签范围 (精确标签/模糊检索词)</label>
          <div class="pills-container" id="pillsContainer">
            <!-- Pills go here -->
            <input type="text" id="pillInput" class="pill-input" placeholder="输入并回车或选择..." autocomplete="off">
            <div id="autocompleteList" class="autocomplete-list"></div>
          </div>
          <div class="muted" style="margin-top: 4px;">输入标签以 # 开头（如 #项目/个人AI知识库），回车可直接添加模糊检索词（如 部署）。</div>
        </div>
        
        <div class="field">
          <label>数据召回范围选择</label>
          <div style="display: flex; flex-wrap: wrap; gap: 16px; margin-top: 6px;">
            <label style="display: flex; align-items: center; gap: 6px; cursor: pointer; user-select: none;">
              <input id="qaIncludeOriginal" type="checkbox" checked style="width: auto; margin: 0;">
              原始 Memo 正文
            </label>
            <label style="display: flex; align-items: center; gap: 6px; cursor: pointer; user-select: none;">
              <input id="qaIncludeAttachments" type="checkbox" checked style="width: auto; margin: 0;">
              关联解析附件大纲
            </label>
            <label style="display: flex; align-items: center; gap: 6px; cursor: pointer; user-select: none;">
              <input id="qaIncludeAiSummary" type="checkbox" checked style="width: auto; margin: 0;">
              AI 整理/标签总结 Memo
            </label>
          </div>
        </div>
        
        <div class="field">
          <label for="qaSystemPrompt">系统提示词 (System Prompt)</label>
          <textarea id="qaSystemPrompt" class="prompt" spellcheck="false" placeholder="输入系统提示词...">你是一个专业的知识库问答助手。请基于提供的【知识库参考上下文】，专业、客观、严谨地回答【用户提问】。如果在上下文中找不到相关内容，请明确告知，不要胡乱编造。</textarea>
        </div>

        <div class="field">
          <label for="qaQuery">用户提问 (Query)</label>
          <textarea id="qaQuery" class="prompt" style="min-height: 80px;" placeholder="输入您的问题..."></textarea>
        </div>

        <div class="toolbar">
          <button id="btnGeneratePrompt" class="primary" type="button">编译并生成 Prompt</button>
        </div>
      </div>

      <div class="panel stack">
        <h2>编译结果 (可直接一键复制)</h2>
        <div class="prompt-container">
          <button id="btnCopyPrompt" class="copy-btn-floating" type="button">一键复制</button>
          <textarea id="assembledPromptOutput" class="prompt" style="min-height: 460px; width: 100%;" readonly placeholder="生成后，完整的 Prompt 内容将在此处显示，可一键复制并粘贴到任意网页大模型进行问答。"></textarea>
        </div>
        <div>
          <h3>召回来源概要 (<span id="retrievedCount">0</span> 个知识片段)</h3>
          <pre id="qaSourcesSummary" style="max-height: 120px; font-size: 0.8rem;">（暂无召回来源）</pre>
        </div>
      </div>
    </div>
  </section>

  <section class="tab-panel" data-panel="reprocess">
    <div class="grid">
      <div class="panel stack">
        <h2>Memo 重新整理与批量处理</h2>
        
        <div style="border-bottom: 1px solid var(--border); padding-bottom: 16px; margin-bottom: 16px;">
          <h3>单条 Memo 重新整理</h3>
          <div class="field">
            <label for="reprocessUrlInput">粘贴 Memos URL 或输入 Memo UID</label>
            <input type="text" id="reprocessUrlInput" placeholder="例如：http://localhost:8080/m/abc 或直接输入 abc" autocomplete="off">
            <div style="margin-top: 6px; display: flex; align-items: center; gap: 8px;">
              <span class="badge" id="reprocessMemoUidBadge" style="display: none; background: var(--accent); color: #fff; padding: 3px 8px; border-radius: 12px; font-size: 0.75rem; font-weight: 600;">解析到的 ID: <span id="reprocessMemoUidText"></span></span>
            </div>
            <div class="muted" style="margin-top: 4px;">输入时，前端会自动通过正则提取 Memo 的 UID 编码，并在重新整理前物理删除对应的旧 AI 整理卡片。</div>
          </div>
          <div class="toolbar" style="margin-top: 10px;">
            <button id="btnReprocessSingle" class="primary" type="button">删除旧整理卡片并重生成</button>
          </div>
        </div>

        <div>
          <h3>按标签批量重新整理</h3>
          <div class="field" style="position: relative;">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px;">
              <label for="reprocessTagInput" style="margin-bottom: 0;">选择业务标签 (支持模糊/拼音搜索)</label>
              <div style="display: flex; align-items: center; gap: 6px;">
                <span style="font-size: 0.8rem; color: var(--muted);">逻辑关系：</span>
                <select id="reprocessTagRelation" style="width: auto; padding: 2px 6px; font-size: 0.8rem; border-radius: 4px;">
                  <option value="OR">或 (OR)</option>
                  <option value="AND">与 (AND)</option>
                </select>
              </div>
            </div>
            <div class="pills-container" id="reprocessTagContainer">
              <input type="text" id="reprocessTagInput" class="pill-input" placeholder="输入标签前缀，如 #项目..." autocomplete="off">
              <div id="reprocessTagAutocomplete" class="autocomplete-list"></div>
            </div>
            <div class="muted" style="margin-top: 4px;">多标签匹配将自动级联（包含子标签）。在“与 (AND)”关系下，Memo 必须包含所选的所有标签；在“或 (OR)”关系下，满足任一标签即可被重整理。</div>
          </div>
          <div class="toolbar" style="margin-top: 10px;">
            <button id="btnReprocessTag" class="primary" type="button">批量删除旧卡片并重整理</button>
          </div>
        </div>
      </div>

      <div class="panel stack">
        <h2>LLM 模型与提示词定制</h2>
        <div class="field">
          <label for="reprocessProvider">选择大模型提供商 (LLM Provider)</label>
          <select id="reprocessProvider">
            <option value="">(使用全局默认)</option>
          </select>
        </div>
        <div class="field">
          <label for="reprocessModelName">模型名称 (Model Name)</label>
          <input type="text" id="reprocessModelName" placeholder="例如：deepseek-chat" autocomplete="off">
        </div>
        
        <details class="field" style="margin-top: 10px;">
          <summary style="cursor: pointer; color: var(--accent); font-weight: 600; font-size: 0.85rem; user-select: none;">展开修改定制提示词 (Prompt Overrides)</summary>
          <div style="margin-top: 10px;" class="stack">
            <div>
              <label for="reprocessSystemPrompt">系统提示词 (System Prompt)</label>
              <textarea id="reprocessSystemPrompt" class="prompt" spellcheck="false" placeholder="留空使用系统默认提示词..."></textarea>
            </div>
            <div>
              <label for="reprocessUserPrompt">用户提示词 (User Prompt)</label>
              <textarea id="reprocessUserPrompt" class="prompt" spellcheck="false" placeholder="留空使用系统默认提示词..."></textarea>
            </div>
          </div>
        </details>

        <div style="border-top: 1px solid var(--border); padding-top: 16px; margin-top: 10px;">
          <h3>执行状态与日志</h3>
          <pre id="reprocessLog" style="max-height: 200px; font-size: 0.8rem; background: var(--codebg);">等待操作...</pre>
          <div id="jumpToJobsContainer" style="display: none; margin-top: 10px;">
            <button id="btnJumpToJobs" class="primary" type="button">查看任务详细日志 ➔</button>
          </div>
        </div>
      </div>
    </div>
  </section>

  <section class="tab-panel" data-panel="logs">
    <div class="panel stack">
      <h2>系统运行日志</h2>
      <div class="hint">实时监控与检索 API、Worker、AI 调用、向量数据库和文档解析的后台运行状态。</div>
      
      <div class="toolbar" style="margin-top: 15px; display: flex; gap: 10px; flex-wrap: wrap; align-items: center;">
        <div class="field" style="margin: 0; flex: 1; min-width: 200px;">
          <input id="logSearchQuery" type="text" placeholder="搜索日志内容..." style="width: 100%; height: 38px;">
        </div>
        <div class="field" style="margin: 0; width: 150px;">
          <select id="logFilterComponent" style="width: 100%; height: 38px;">
            <option value="">所有组件</option>
            <option value="system">System (系统)</option>
            <option value="api">API (接口)</option>
            <option value="worker">Worker (工作流)</option>
            <option value="ai">AI (大模型)</option>
            <option value="vector">Vector (向量)</option>
            <option value="mineru">MinerU (文档解析)</option>
          </select>
        </div>
        <div class="field" style="margin: 0; width: 120px;">
          <select id="logFilterLevel" style="width: 100%; height: 38px;">
            <option value="">所有级别</option>
            <option value="DEBUG">DEBUG</option>
            <option value="INFO">INFO</option>
            <option value="WARNING">WARNING</option>
            <option value="ERROR">ERROR</option>
          </select>
        </div>
        <button id="refreshLogsButton" class="primary" type="button" style="height: 38px;">刷新</button>
        <button id="clearLogsButton" class="danger" type="button" style="height: 38px;">清空日志</button>
        <label style="display: flex; align-items: center; gap: 5px; font-size: 14px; user-select: none; margin-left: 5px;">
          <input id="logAutoRefresh" type="checkbox" checked> 实时监听
        </label>
      </div>
      
      <div style="margin-top: 15px; max-height: 520px; min-height: 300px; overflow-y: auto; background: #1e1e1e; color: #d4d4d4; font-family: 'Fira Code', 'Courier New', Courier, monospace; padding: 15px; border-radius: 8px; border: 1px solid #333; line-height: 1.5; font-size: 0.85rem;" id="logTerminal">
        <div id="logContent">等待加载日志...</div>
      </div>
      
      <div class="toolbar" style="margin-top: 10px; display: flex; justify-content: space-between; align-items: center;">
        <span id="logCountLabel" style="font-size: 14px; color: var(--text-light);">共 0 条日志</span>
        <div style="display: flex; gap: 5px;">
          <button id="logPrevPage" type="button" disabled>上一页</button>
          <button id="logNextPage" type="button" disabled>下一页</button>
        </div>
      </div>
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
const remindersEnabled = document.getElementById("remindersEnabled");
const remindersTriggerTag = document.getElementById("remindersTriggerTag");
const remindersConfidence = document.getElementById("remindersConfidence");
const remindersTimeout = document.getElementById("remindersTimeout");
const remindersWebhookUrl = document.getElementById("remindersWebhookUrl");
const saveRemindersConfigButton = document.getElementById("saveRemindersConfigButton");
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
  docparser: { panel: "docparser" },
  backup: { panel: "backup" },
  memos: { panel: "memos" },
  "vector-search": { panel: "vector-search" },
  qa: { panel: "qa" },
  reprocess: { panel: "reprocess" },
  logs: { panel: "logs" }
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
  
  if (nextName === "logs") {
    loadLogs();
    setupLogsInterval();
  } else {
    if (logAutoRefreshInterval) {
      clearInterval(logAutoRefreshInterval);
      logAutoRefreshInterval = null;
    }
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
    const verDisp = document.getElementById("version-display");
    if (verDisp && data.version) {
      verDisp.textContent = `v${data.version}` + (data.commit_hash ? ` (${data.commit_hash})` : "");
    }
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
    
    // Pre-populate reprocess prompts
    const reprocSys = document.getElementById("reprocessSystemPrompt");
    const reprocUsr = document.getElementById("reprocessUserPrompt");
    if (reprocSys) reprocSys.value = data.organize_memo.system || "";
    if (reprocUsr) reprocUsr.value = data.organize_memo.user || "";

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
    
    // Populate reprocess LLM providers
    const reprocProv = document.getElementById("reprocessProvider");
    if (reprocProv) {
      reprocProv.replaceChildren(
        (() => {
          const opt = document.createElement("option");
          opt.value = "";
          opt.textContent = "(使用全局默认)";
          return opt;
        })(),
        ...modelProviders.map((provider) => {
          const option = document.createElement("option");
          option.value = provider.name;
          option.textContent = provider.name;
          return option;
        })
      );
      reprocProv.value = "";
    }

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

let tagSummarySelectedTags = [];
let tagSummaryAvailableTags = [];

const tagSummaryTagContainer = document.getElementById("tagSummaryTagContainer");
const tagSummaryTagRelation = document.getElementById("tagSummaryTagRelation");
const tagSummaryTagInput = document.getElementById("tagSummaryTagInput");
const tagSummaryTagAutocomplete = document.getElementById("tagSummaryTagAutocomplete");

function renderTagSummaryPills() {
  const pills = tagSummaryTagContainer.querySelectorAll(".pill");
  pills.forEach((p) => p.remove());

  for (const tag of tagSummarySelectedTags) {
    const pill = document.createElement("span");
    pill.className = "pill";
    pill.textContent = tag;
    const remove = document.createElement("span");
    remove.className = "remove";
    remove.textContent = "×";
    remove.onclick = (e) => {
      e.stopPropagation();
      tagSummarySelectedTags = tagSummarySelectedTags.filter((t) => t !== tag);
      renderTagSummaryPills();
    };
    pill.append(remove);
    tagSummaryTagContainer.insertBefore(pill, tagSummaryTagInput);
  }
}

function addTagSummaryPill(tag) {
  const val = tag.trim();
  if (!val) return;
  if (!tagSummarySelectedTags.includes(val)) {
    tagSummarySelectedTags.push(val);
    renderTagSummaryPills();
  }
  tagSummaryTagInput.value = "";
  tagSummaryTagAutocomplete.style.display = "none";
}

async function loadTagSummaryBusinessTags() {
  try {
    const tags = await requestJson("/admin/tags/business");
    if (Array.isArray(tags)) {
      tagSummaryAvailableTags = tags;
    }
  } catch (e) {
    console.warn("Failed to load business tags for summary:", e);
  }
}

tagSummaryTagInput.addEventListener("input", () => {
  const val = tagSummaryTagInput.value.trim().toLowerCase();
  if (!val) {
    tagSummaryTagAutocomplete.style.display = "none";
    return;
  }
  const matches = tagSummaryAvailableTags.filter(t => t.toLowerCase().includes(val) && !tagSummarySelectedTags.includes(t));
  if (matches.length === 0) {
    tagSummaryTagAutocomplete.style.display = "none";
    return;
  }
  tagSummaryTagAutocomplete.replaceChildren(
    ...matches.map(m => {
      const div = document.createElement("div");
      div.className = "autocomplete-item";
      div.textContent = m;
      div.onclick = () => {
        addTagSummaryPill(m);
      };
      return div;
    })
  );
  tagSummaryTagAutocomplete.style.display = "block";
});

tagSummaryTagInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    e.preventDefault();
    addTagSummaryPill(tagSummaryTagInput.value);
  } else if (e.key === "Backspace" && !tagSummaryTagInput.value && tagSummarySelectedTags.length > 0) {
    tagSummarySelectedTags.pop();
    renderTagSummaryPills();
  }
});

document.addEventListener("click", (e) => {
  if (e.target !== tagSummaryTagInput && e.target !== tagSummaryTagAutocomplete) {
    tagSummaryTagAutocomplete.style.display = "none";
  }
});

async function createTagSummary() {
  try {
    const text = tagSummaryTagInput.value.trim();
    if (text) {
      addTagSummaryPill(text);
    }

    if (tagSummarySelectedTags.length === 0) {
      setNotice("错误：请选择或输入至少一个用于标签总结的业务标签！", "error");
      return;
    }

    const limit = Number(document.getElementById("tagSummaryLimit").value || "50");
    const relation = tagSummaryTagRelation.value;

    const data = await requestJson("/admin/tag-summaries", {
      method: "POST",
      body: JSON.stringify({
        tags: tagSummarySelectedTags,
        relation: relation,
        limit: limit
      })
    });
    tagSummaryOutput.textContent = JSON.stringify(data, null, 2);
    showDetail(data);
    setNotice(`标签总结已生成：memos/${data.summary_memo_uid}`, "ok");
    
    tagSummarySelectedTags = [];
    renderTagSummaryPills();
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

async function resetDatabase() {
  if (!window.confirm("危险！此操作将永久删除 Sidecar 的所有本地数据（不影响 Memos 主站数据）。确认重置？")) {
    return;
  }
  const confirmText = window.prompt("请输入 'RESET' 以确认重置操作：");
  if (confirmText !== "RESET") {
    setNotice("操作已取消：确认字符不正确", "warn");
    return;
  }
  try {
    const data = await requestJson("/admin/database/reset", { method: "POST" });
    setNotice(data.message, "ok");
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

async function loadRemindersConfig() {
  try {
    const data = await requestJson("/admin/reminders/config");
    remindersEnabled.checked = data.enabled;
    remindersTriggerTag.value = data.trigger_tag;
    remindersConfidence.value = data.confidence_threshold;
    remindersTimeout.value = data.request_timeout_seconds;
    remindersWebhookUrl.value = "";
    if (data.webhook_url_present) {
      remindersWebhookUrl.placeholder = "已配置 Webhook URL（留空保持不变）";
    } else {
      remindersWebhookUrl.placeholder = "留空保持不变，或输入新 URL/Bark Key";
    }
  } catch (error) {
    setNotice(String(error.message || error), "error");
  }
}

async function saveRemindersConfig() {
  try {
    const payload = {
      enabled: remindersEnabled.checked,
      trigger_tag: remindersTriggerTag.value.trim(),
      confidence_threshold: parseFloat(remindersConfidence.value),
      request_timeout_seconds: parseFloat(remindersTimeout.value),
      webhook_url: remindersWebhookUrl.value.trim() || null
    };
    const data = await requestJson("/admin/reminders/config", {
      method: "PUT",
      body: JSON.stringify(payload)
    });
    setNotice("提醒配置保存成功", "ok");
    await loadRemindersConfig();
  } catch (error) {
    setNotice(String(error.message || error), "error");
  }
}

async function loadVectorSearchConfig() {
  try {
    const data = await requestJson("/admin/vector-search/config");
    document.getElementById("vectorSearchEnabled").checked = data.enabled;
    document.getElementById("vectorSearchModel").value = data.model;
    document.getElementById("vectorSearchBaseUrl").value = data.base_url;
    document.getElementById("vectorSearchApiKey").value = "";
    if (data.api_key_present) {
      document.getElementById("vectorSearchApiKey").placeholder = `已配置（留空保持不变，写入 ${data.api_key_env}）`;
    } else {
      document.getElementById("vectorSearchApiKey").placeholder = `留空保持不变，或输入新 Key 保存至 ${data.api_key_env}`;
    }
  } catch (error) {
    setNotice(String(error.message || error), "error");
  }
}

async function saveVectorSearchConfig() {
  try {
    const payload = {
      enabled: document.getElementById("vectorSearchEnabled").checked,
      api_key_env: "SILICONFLOW_API_KEY",
      base_url: document.getElementById("vectorSearchBaseUrl").value.trim() || "https://api.siliconflow.cn/v1",
      model: document.getElementById("vectorSearchModel").value.trim() || "BAAI/bge-m3",
      api_key: document.getElementById("vectorSearchApiKey").value.trim() || null
    };
    const data = await requestJson("/admin/vector-search/config", {
      method: "PUT",
      body: JSON.stringify(payload)
    });
    setNotice("向量库配置保存成功", "ok");
    await loadVectorSearchConfig();
  } catch (error) {
    setNotice(String(error.message || error), "error");
  }
}

document.getElementById("saveVectorSearchConfigButton").addEventListener("click", saveVectorSearchConfig);

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
document.getElementById("resetDatabaseButton").addEventListener("click", resetDatabase);
document.getElementById("refreshDocParserButton").addEventListener("click", loadDocumentParser);
document.getElementById("saveDocParserButton").addEventListener("click", saveDocumentParser);
saveRemindersConfigButton.addEventListener("click", saveRemindersConfig);
/* Memos 整合配置逻辑 */
const memosBaseUrl = document.getElementById("memosBaseUrl");
const memosApiToken = document.getElementById("memosApiToken");
const memosTokenStatus = document.getElementById("memosTokenStatus");
let memosBaseUrlEnv = "MEMOS_BASE_URL";
let memosApiTokenEnv = "MEMOS_API_TOKEN";

async function loadMemosConfig() {
  try {
    const data = await requestJson("/admin/memos/config");
    memosBaseUrl.value = data.base_url || "";
    memosApiToken.value = "";
    memosBaseUrlEnv = data.base_url_env || "MEMOS_BASE_URL";
    memosApiTokenEnv = data.api_token_env || "MEMOS_API_TOKEN";
    memosTokenStatus.textContent = data.api_token_present ? "Token 已配置" : "Token 未配置";
    setNotice("Memos 同步配置已刷新", "ok");
  } catch (error) {
    setNotice(String(error.message || error), "error");
  }
}

async function saveMemosConfig() {
  try {
    const payload = {
      base_url: memosBaseUrl.value.trim(),
      api_token_env: memosApiTokenEnv,
      base_url_env: memosBaseUrlEnv,
    };
    if (memosApiToken.value.trim()) {
      payload.api_token = memosApiToken.value.trim();
    }
    const data = await requestJson("/admin/memos/config", {
      method: "PUT",
      body: JSON.stringify(payload),
    });
    memosBaseUrl.value = data.base_url || "";
    memosApiToken.value = "";
    memosTokenStatus.textContent = data.api_token_present ? "Token 已配置" : "Token 未配置";
    await loadHealth();
    setNotice("Memos 同步配置已保存", "ok");
  } catch (error) {
    setNotice(String(error.message || error), "error");
  }
}

document.getElementById("refreshMemosConfigButton").addEventListener("click", loadMemosConfig);
document.getElementById("saveMemosConfigButton").addEventListener("click", saveMemosConfig);

async function deleteAllMemos() {
  if (!window.confirm("🚨 警告！此操作将永久删除 Memos 主站中当前用户的所有笔记，并清空 Sidecar 本地同步记录。确认删除？")) {
    return;
  }
  const confirmText = window.prompt("请输入 'DELETE ALL MEMOS' 以确认删除操作：");
  if (confirmText !== "DELETE ALL MEMOS") {
    setNotice("操作已取消：确认字符不正确", "warn");
    return;
  }
  try {
    setNotice("正在删除全部 Memos，请稍候...", "warn");
    const data = await requestJson("/admin/memos/delete-all", { method: "POST" });
    setNotice(data.message, "ok");
    await Promise.all([loadJobs(), loadCandidates(), loadReminders(), loadHealth()]);
  } catch (error) {
    setNotice(String(error.message || error), "error");
  }
}

document.getElementById("deleteAllMemosButton").addEventListener("click", deleteAllMemos);



/* 系统日志模块逻辑 */
let logCurrentPage = 0;
const logLimit = 150;
let logAutoRefreshInterval = null;

const logSearchQuery = document.getElementById("logSearchQuery");
const logFilterComponent = document.getElementById("logFilterComponent");
const logFilterLevel = document.getElementById("logFilterLevel");
const logTerminal = document.getElementById("logTerminal");
const logContent = document.getElementById("logContent");
const logCountLabel = document.getElementById("logCountLabel");
const logPrevPage = document.getElementById("logPrevPage");
const logNextPage = document.getElementById("logNextPage");
const logAutoRefresh = document.getElementById("logAutoRefresh");

async function loadLogs(isAuto = false) {
  try {
    const query = new URLSearchParams({
      limit: logLimit,
      offset: logCurrentPage * logLimit
    });
    
    const searchVal = logSearchQuery.value.trim();
    const componentVal = logFilterComponent.value;
    const levelVal = logFilterLevel.value;
    
    if (searchVal) query.set("query", searchVal);
    if (componentVal) query.set("component", componentVal);
    if (levelVal) query.set("level", levelVal);
    
    const data = await requestJson(`/admin/logs?${query.toString()}`);
    
    if (data.logs.length === 0) {
      logContent.innerHTML = '<div style="color: var(--text-light); text-align: center; padding: 20px;">暂无日志记录</div>';
    } else {
      // Map and join each formatted log line
      logContent.innerHTML = data.logs.map(renderLogLine).join("");
      
      // Auto scroll to bottom on real-time listening
      if (logAutoRefresh.checked) {
        setTimeout(() => {
          logTerminal.scrollTop = logTerminal.scrollHeight;
        }, 50);
      }
    }
    
    logCountLabel.textContent = `共 ${data.total_count} 条日志 (当前显示第 ${logCurrentPage + 1} 页)`;
    logPrevPage.disabled = logCurrentPage === 0;
    logNextPage.disabled = (logCurrentPage + 1) * logLimit >= data.total_count;
    
    if (!isAuto) {
      setNotice(`日志已刷新：加载了 ${data.logs.length} 条记录`, "ok");
    }
  } catch (error) {
    if (!isAuto) {
      setNotice(String(error.message || error), "error");
      logContent.textContent = String(error.message || error);
    }
  }
}

function renderLogLine(log) {
  // Style log levels
  let levelColor = "#909399";
  if (log.level === "INFO") levelColor = "#52c41a";
  else if (log.level === "WARNING") levelColor = "#faad14";
  else if (log.level === "ERROR") levelColor = "#ff4d4f";
  
  const levelSpan = `<span style="color: ${levelColor}; font-weight: bold;">[${log.level}]</span>`;
  
  // Style components
  let compColor = "#909399";
  let compText = log.component.toUpperCase();
  if (log.component === "api") compColor = "#1890ff";
  else if (log.component === "worker") compColor = "#fa8c16";
  else if (log.component === "ai") { compColor = "#722ed1"; compText = "AI"; }
  else if (log.component === "vector") { compColor = "#13c2c2"; compText = "VECTOR"; }
  else if (log.component === "mineru") { compColor = "#eb2f96"; compText = "MINERU"; }
  
  const compSpan = `<span style="background: ${compColor}; color: #fff; padding: 1px 6px; border-radius: 4px; font-size: 0.75rem; font-weight: bold; margin-right: 4px;">${compText}</span>`;
  
  // Format timestamp
  const cleanTime = log.timestamp.replace("T", " ").substring(0, 19);
  const timeSpan = `<span style="color: #8c8c8c;">${cleanTime}</span>`;
  
  // Escape message HTML
  const escapedMessage = log.message
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
    
  return `<div style="margin-bottom: 4px; white-space: pre-wrap; word-break: break-all;">${timeSpan} ${levelSpan} ${compSpan} ${escapedMessage}</div>`;
}

async function clearLogs() {
  if (!window.confirm("⚠️ 确认要清空数据库中的所有运行日志吗？该操作不可恢复！")) {
    return;
  }
  try {
    setNotice("正在清空系统日志...", "warn");
    const data = await requestJson("/admin/logs/clear", { method: "POST" });
    setNotice(data.message, "ok");
    logCurrentPage = 0;
    await loadLogs();
  } catch (error) {
    setNotice(String(error.message || error), "error");
  }
}

function setupLogsInterval() {
  if (logAutoRefreshInterval) {
    clearInterval(logAutoRefreshInterval);
    logAutoRefreshInterval = null;
  }
  if (logAutoRefresh.checked) {
    logAutoRefreshInterval = setInterval(() => {
      const activeTab = document.querySelector(".tabs .tab.active");
      if (activeTab && activeTab.dataset.tabTarget === "logs") {
        loadLogs(true);
      }
    }, 2000);
  }
}

document.getElementById("refreshLogsButton").addEventListener("click", () => {
  logCurrentPage = 0;
  loadLogs();
});
document.getElementById("clearLogsButton").addEventListener("click", clearLogs);
logPrevPage.addEventListener("click", () => {
  if (logCurrentPage > 0) {
    logCurrentPage--;
    loadLogs();
  }
});
logNextPage.addEventListener("click", () => {
  logCurrentPage++;
  loadLogs();
});
logSearchQuery.addEventListener("input", () => {
  logCurrentPage = 0;
  loadLogs();
});
logFilterComponent.addEventListener("change", () => {
  logCurrentPage = 0;
  loadLogs();
});
logFilterLevel.addEventListener("change", () => {
  logCurrentPage = 0;
  loadLogs();
});
logAutoRefresh.addEventListener("change", setupLogsInterval);



/* 文档解析（MinerU）配置逻辑 */
const dpProvider = document.getElementById("dpProvider");
const dpBaseUrl = document.getElementById("dpBaseUrl");
const dpTokenEnv = document.getElementById("dpTokenEnv");
const dpApiKey = document.getElementById("dpApiKey");
const dpKeyStatus = document.getElementById("dpKeyStatus");
const dpModelVersion = document.getElementById("dpModelVersion");
const dpLanguage = document.getElementById("dpLanguage");
const dpTimeout = document.getElementById("dpTimeout");
const dpPollInterval = document.getElementById("dpPollInterval");
const dpMaxPolls = document.getElementById("dpMaxPolls");
const dpEnableTable = document.getElementById("dpEnableTable");
const dpEnableFormula = document.getElementById("dpEnableFormula");
const dpIsOcr = document.getElementById("dpIsOcr");

async function loadDocumentParser() {
  try {
    const data = await requestJson("/admin/document-parser");
    dpProvider.value = data.provider || "mineru";
    dpBaseUrl.value = data.base_url || "";
    dpTokenEnv.value = data.token_env || "";
    dpApiKey.value = "";
    dpKeyStatus.textContent = data.api_key_present ? "Key 已配置" : "Key 未配置";
    dpModelVersion.value = data.model_version || "vlm";
    dpLanguage.value = data.language || "ch";
    dpTimeout.value = data.timeout_seconds ?? 60;
    dpPollInterval.value = data.poll_interval_seconds ?? 3;
    dpMaxPolls.value = data.max_polls ?? 60;
    dpEnableTable.checked = data.enable_table !== false;
    dpEnableFormula.checked = data.enable_formula !== false;
    dpIsOcr.checked = !!data.is_ocr;
    setNotice("文档解析配置已刷新", "ok");
  } catch (error) {
    setNotice(String(error.message || error), "error");
  }
}

async function saveDocumentParser() {
  try {
    const payload = {
      provider: dpProvider.value,
      base_url: dpBaseUrl.value,
      token_env: dpTokenEnv.value,
      timeout_seconds: Number(dpTimeout.value || "60"),
      poll_interval_seconds: Number(dpPollInterval.value || "3"),
      max_polls: Number(dpMaxPolls.value || "60"),
      model_version: dpModelVersion.value,
      language: dpLanguage.value,
      enable_table: dpEnableTable.checked,
      enable_formula: dpEnableFormula.checked,
      is_ocr: dpIsOcr.checked,
    };
    if (dpApiKey.value.trim()) {
      payload.api_key = dpApiKey.value.trim();
    }
    const data = await requestJson("/admin/document-parser", {
      method: "PUT",
      body: JSON.stringify(payload),
    });
    dpProvider.value = data.provider || "mineru";
    dpBaseUrl.value = data.base_url || "";
    dpTokenEnv.value = data.token_env || "";
    dpApiKey.value = "";
    dpKeyStatus.textContent = data.api_key_present ? "Key 已配置" : "Key 未配置";
    dpModelVersion.value = data.model_version || "vlm";
    dpLanguage.value = data.language || "ch";
    dpTimeout.value = data.timeout_seconds ?? 60;
    dpPollInterval.value = data.poll_interval_seconds ?? 3;
    dpMaxPolls.value = data.max_polls ?? 60;
    dpEnableTable.checked = data.enable_table !== false;
    dpEnableFormula.checked = data.enable_formula !== false;
    dpIsOcr.checked = !!data.is_ocr;
    await loadHealth();
    setNotice("文档解析配置已保存", "ok");
  } catch (error) {
    setNotice(String(error.message || error), "error");
  }
}

/* QA 离线问答 & Prompt 编译器逻辑 */
let qaSelectedTags = [];
let qaAvailableTags = [];

const pillsContainer = document.getElementById("pillsContainer");
const pillInput = document.getElementById("pillInput");
const autocompleteList = document.getElementById("autocompleteList");
const btnGeneratePrompt = document.getElementById("btnGeneratePrompt");
const btnCopyPrompt = document.getElementById("btnCopyPrompt");
const qaSystemPrompt = document.getElementById("qaSystemPrompt");
const qaQuery = document.getElementById("qaQuery");
const assembledPromptOutput = document.getElementById("assembledPromptOutput");
const retrievedCount = document.getElementById("retrievedCount");
const qaSourcesSummary = document.getElementById("qaSourcesSummary");

const qaIncludeOriginal = document.getElementById("qaIncludeOriginal");
const qaIncludeAttachments = document.getElementById("qaIncludeAttachments");
const qaIncludeAiSummary = document.getElementById("qaIncludeAiSummary");

function renderPills() {
  const pills = pillsContainer.querySelectorAll(".pill");
  for (const p of pills) {
    p.remove();
  }
  for (const tag of qaSelectedTags) {
    const pill = document.createElement("div");
    pill.className = "pill";
    pill.textContent = tag;
    const remove = document.createElement("span");
    remove.className = "remove";
    remove.textContent = "×";
    remove.onclick = (e) => {
      e.stopPropagation();
      qaSelectedTags = qaSelectedTags.filter((t) => t !== tag);
      renderPills();
    };
    pill.append(remove);
    pillsContainer.insertBefore(pill, pillInput);
  }
}

function addPill(tag) {
  const val = tag.trim();
  if (!val) return;
  if (!qaSelectedTags.includes(val)) {
    qaSelectedTags.push(val);
    renderPills();
  }
  pillInput.value = "";
  autocompleteList.style.display = "none";
}

async function loadQABusinessTags() {
  try {
    const tags = await requestJson("/admin/tags/business");
    if (Array.isArray(tags)) {
      qaAvailableTags = tags;
    }
  } catch (e) {
    console.warn("Failed to load business tags:", e);
  }
}

pillInput.addEventListener("input", () => {
  const val = pillInput.value.trim().toLowerCase();
  if (!val) {
    autocompleteList.style.display = "none";
    return;
  }
  const matches = qaAvailableTags.filter(
    (t) => t.toLowerCase().includes(val) && !qaSelectedTags.includes(t)
  );
  if (matches.length === 0) {
    autocompleteList.style.display = "none";
    return;
  }
  autocompleteList.replaceChildren(
    ...matches.map((m) => {
      const div = document.createElement("div");
      div.className = "autocomplete-item";
      div.textContent = m;
      div.onclick = () => addPill(m);
      return div;
    })
  );
  autocompleteList.style.display = "block";
});

pillInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    e.preventDefault();
    addPill(pillInput.value);
  } else if (e.key === "Backspace" && !pillInput.value && qaSelectedTags.length > 0) {
    qaSelectedTags.pop();
    renderPills();
  }
});

document.addEventListener("click", (e) => {
  if (!pillsContainer.contains(e.target)) {
    autocompleteList.style.display = "none";
  }
});

pillsContainer.addEventListener("click", () => {
  pillInput.focus();
});

btnGeneratePrompt.addEventListener("click", async () => {
  const system = qaSystemPrompt.value.trim();
  const query = qaQuery.value.trim();
  if (!query) {
    alert("请输入提问内容！");
    return;
  }
  btnGeneratePrompt.disabled = true;
  btnGeneratePrompt.textContent = "编译中...";
  try {
    const data = await requestJson("/admin/qa/generate-prompt", {
      method: "POST",
      body: JSON.stringify({
        tags: qaSelectedTags,
        system_prompt: system,
        query: query,
        include_original: qaIncludeOriginal.checked,
        include_attachments: qaIncludeAttachments.checked,
        include_ai_summary: qaIncludeAiSummary.checked
      })
    });
    assembledPromptOutput.value = data.assembled_prompt;
    retrievedCount.textContent = data.retrieved_count;
    if (data.sources && data.sources.length > 0) {
      qaSourcesSummary.textContent = JSON.stringify(data.sources, null, 2);
    } else {
      qaSourcesSummary.textContent = "（未找到符合所选标签或检索词的知识库内容）";
    }
    setNotice("Prompt 编译生成成功，已展示在右侧区域！", "ok");
  } catch (err) {
    setNotice("QA Prompt 编译失败：" + String(err.message || err), "error");
  } finally {
    btnGeneratePrompt.disabled = false;
    btnGeneratePrompt.textContent = "编译并生成 Prompt";
  }
});

btnCopyPrompt.addEventListener("click", () => {
  const text = assembledPromptOutput.value;
  if (!text) {
    alert("没有可复制的内容！请先编译生成 Prompt。");
    return;
  }
  navigator.clipboard.writeText(text).then(
    () => {
      btnCopyPrompt.textContent = "✓ 已复制！";
      btnCopyPrompt.style.background = "var(--ok)";
      setTimeout(() => {
        btnCopyPrompt.textContent = "一键复制";
        btnCopyPrompt.style.background = "var(--accent)";
      }, 2000);
    },
    (err) => {
      alert("复制失败，请手动选择复制：" + err);
    }
  );
});

/* 重新整理与批量处理逻辑 */
let reprocessSelectedTags = [];
let reprocessAvailableTags = [];

const reprocessUrlInput = document.getElementById("reprocessUrlInput");
const reprocessMemoUidBadge = document.getElementById("reprocessMemoUidBadge");
const reprocessMemoUidText = document.getElementById("reprocessMemoUidText");
const btnReprocessSingle = document.getElementById("btnReprocessSingle");

const reprocessTagContainer = document.getElementById("reprocessTagContainer");
const reprocessTagRelation = document.getElementById("reprocessTagRelation");
const reprocessTagInput = document.getElementById("reprocessTagInput");
const reprocessTagAutocomplete = document.getElementById("reprocessTagAutocomplete");
const btnReprocessTag = document.getElementById("btnReprocessTag");

const reprocessProvider = document.getElementById("reprocessProvider");
const reprocessModelName = document.getElementById("reprocessModelName");
const reprocessSystemPrompt = document.getElementById("reprocessSystemPrompt");
const reprocessUserPrompt = document.getElementById("reprocessUserPrompt");
const reprocessLog = document.getElementById("reprocessLog");

const jumpToJobsContainer = document.getElementById("jumpToJobsContainer");
const btnJumpToJobs = document.getElementById("btnJumpToJobs");

// 1. URL 自动解析并提取 UID
reprocessUrlInput.addEventListener("input", () => {
  const val = reprocessUrlInput.value.trim();
  if (!val) {
    reprocessMemoUidBadge.style.display = "none";
    return;
  }
  const match = val.match(/(?:\\/m\\/|\\/memos\\/|^)([A-Za-z0-9_-]+)/);
  const uid = match ? match[1] : val;
  if (uid && uid.length >= 6) {
    reprocessMemoUidText.textContent = uid;
    reprocessMemoUidBadge.style.display = "inline-flex";
  } else {
    reprocessMemoUidBadge.style.display = "none";
  }
});

// 2. 标签模糊/首字母匹配联想逻辑
async function loadReprocessBusinessTags() {
  try {
    const tags = await requestJson("/admin/tags/business");
    if (Array.isArray(tags)) {
      reprocessAvailableTags = tags;
    }
  } catch (e) {
    console.warn("Failed to load business tags for reprocessing:", e);
  }
}

function renderReprocessPills() {
  const pills = reprocessTagContainer.querySelectorAll(".pill");
  pills.forEach((p) => p.remove());

  for (const tag of reprocessSelectedTags) {
    const pill = document.createElement("span");
    pill.className = "pill";
    pill.textContent = tag;
    const remove = document.createElement("span");
    remove.className = "remove";
    remove.textContent = "×";
    remove.onclick = (e) => {
      e.stopPropagation();
      reprocessSelectedTags = reprocessSelectedTags.filter((t) => t !== tag);
      renderReprocessPills();
    };
    pill.append(remove);
    reprocessTagContainer.insertBefore(pill, reprocessTagInput);
  }
}

function addReprocessPill(tag) {
  const val = tag.trim();
  if (!val) return;
  if (!reprocessSelectedTags.includes(val)) {
    reprocessSelectedTags.push(val);
    renderReprocessPills();
  }
  reprocessTagInput.value = "";
  reprocessTagAutocomplete.style.display = "none";
}

reprocessTagInput.addEventListener("input", () => {
  const val = reprocessTagInput.value.trim().toLowerCase();
  if (!val) {
    reprocessTagAutocomplete.style.display = "none";
    return;
  }
  
  // 智能模糊过滤并排除已选
  const matches = reprocessAvailableTags.filter(t => t.toLowerCase().includes(val) && !reprocessSelectedTags.includes(t));
  if (matches.length === 0) {
    reprocessTagAutocomplete.style.display = "none";
    return;
  }
  
  reprocessTagAutocomplete.replaceChildren(
    ...matches.map(m => {
      const div = document.createElement("div");
      div.className = "autocomplete-item";
      div.textContent = m;
      div.onclick = () => {
        addReprocessPill(m);
      };
      return div;
    })
  );
  reprocessTagAutocomplete.style.display = "block";
});

reprocessTagInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    e.preventDefault();
    addReprocessPill(reprocessTagInput.value);
  } else if (e.key === "Backspace" && !reprocessTagInput.value && reprocessSelectedTags.length > 0) {
    reprocessSelectedTags.pop();
    renderReprocessPills();
  }
});

// 点击外部时关闭模糊联想框
document.addEventListener("click", (e) => {
  if (e.target !== reprocessTagInput && e.target !== reprocessTagAutocomplete) {
    reprocessTagAutocomplete.style.display = "none";
  }
});

function logReprocess(msg, isError = false) {
  reprocessLog.textContent = msg;
  reprocessLog.style.color = isError ? "var(--danger)" : "var(--fg)";
}

// 3. 单条 Memo 重整理提交
btnReprocessSingle.addEventListener("click", async () => {
  const val = reprocessUrlInput.value.trim();
  if (!val) {
    logReprocess("错误：请输入 Memos URL 或者是 Memo UID！", true);
    return;
  }
  const match = val.match(/(?:\\/m\\/|\\/memos\\/|^)([A-Za-z0-9_-]+)/);
  const uid = match ? match[1] : val;
  
  btnReprocessSingle.disabled = true;
  btnReprocessSingle.textContent = "提交中...";
  logReprocess(`正在分析 Memo '${uid}' 并物理清理旧整理卡片，请稍候...`);
  
  try {
    const payload = {
      memo_url_or_uid: uid,
      model_provider: reprocessProvider.value || null,
      model_name: reprocessModelName.value.trim() || null,
      prompt_override: {
        system: reprocessSystemPrompt.value.trim() || null,
        user: reprocessUserPrompt.value.trim() || null
      }
    };
    
    const res = await requestJson("/admin/jobs/reprocess-memo", {
      method: "POST",
      body: JSON.stringify(payload)
    });
    
    logReprocess(`🎉 成功拉起重新整理任务！\n\n- 任务 ID: ${res.job_id}\n- 任务状态: ${res.status} (已进入队列)\n- 删除的旧 AI 整理卡片: ${res.old_summaries_deleted.join(", ") || "无"}\n\n后台 Worker 正在并发重新分析中，稍后可在 Memos 查看！`);
    jumpToJobsContainer.style.display = "block";
  } catch (err) {
    logReprocess(`错误：${err.message || err}`, true);
  } finally {
    btnReprocessSingle.disabled = false;
    btnReprocessSingle.textContent = "删除旧整理卡片并重生成";
  }
});

// 4. 标签批量重新整理提交
btnReprocessTag.addEventListener("click", async () => {
  // 如果输入框有字，先补进 Pills 里
  const text = reprocessTagInput.value.trim();
  if (text) {
    addReprocessPill(text);
  }

  if (reprocessSelectedTags.length === 0) {
    logReprocess("错误：请选择或输入至少一个需要批量重新整理的业务标签！", true);
    return;
  }

  const tagsStr = reprocessSelectedTags.join(", ");
  const relStr = reprocessTagRelation.value === "AND" ? "与 (AND)" : "或 (OR)";
  
  if (!confirm(`⚠️ 极其重要提示：\n\n确认要批量处理包含标签 ${tagsStr} [关系为 ${relStr}] 的所有 Memos 吗？\n这将会物理删除所有相关的旧 AI 整理卡片，并生成全新整理计划任务！`)) {
    return;
  }
  
  btnReprocessTag.disabled = true;
  btnReprocessTag.textContent = "批量任务提交中...";
  logReprocess(`正在查询匹配标签 [${tagsStr}] [${relStr}] 的所有 Memo，并执行历史数据清理中...`);
  
  try {
    const payload = {
      tags: reprocessSelectedTags,
      relation: reprocessTagRelation.value,
      model_provider: reprocessProvider.value || null,
      model_name: reprocessModelName.value.trim() || null,
      prompt_override: {
        system: reprocessSystemPrompt.value.trim() || null,
        user: reprocessUserPrompt.value.trim() || null
      }
    };
    
    const res = await requestJson("/admin/jobs/batch-reprocess-tag", {
      method: "POST",
      body: JSON.stringify(payload)
    });
    
    logReprocess(`🎉 标签批量重整理任务注册成功！\n\n- 匹配到的 Memo 记录数: ${res.matched_memo_count}\n- 成功启动重新整理任务数: ${res.jobs_created}\n- 物理清理历史卡片数: ${res.old_summaries_deleted_count}\n- 任务 ID 列表: ${res.job_ids.join(", ") || "无"}\n\n批量任务已经就绪，后台协程正在极速并发处理！`);
    
    // 清空选中的标签
    reprocessSelectedTags = [];
    renderReprocessPills();
    
    jumpToJobsContainer.style.display = "block";
  } catch (err) {
    logReprocess(`错误：${err.message || err}`, true);
  } finally {
    btnReprocessTag.disabled = false;
    btnReprocessTag.textContent = "批量删除旧卡片并重整理";
  }
});

btnJumpToJobs.addEventListener("click", () => {
  window.location.hash = "jobs";
});

tokenInput.value = localStorage.getItem(storageKey) || "";
loadHealth();
if (token()) {
  loadJobs();
  loadCandidates();
  loadReminders();
  loadRemindersConfig();
  loadVectorSearchConfig();
  loadPrompts();
  loadModels();
  loadDocumentParser();
  loadQABusinessTags();
  loadReprocessBusinessTags();
  loadTagSummaryBusinessTags();
  renderTagSummaryPills();
  loadMemosConfig();
  loadLogs();
}

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

window.addEventListener("hashchange", showPanelFromHash);
showPanelFromHash();
</script>
</body>
</html>
"""
