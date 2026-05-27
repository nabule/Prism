from __future__ import annotations


TEAMS_UI_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Prism (棱镜) · 团队知识库</title>
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
    .shell { max-width: 1280px; margin: 0 auto; padding: 20px; }
    h1 { margin: 0; font-size: 1.45rem; line-height: 1.2; }
    h2 { margin: 0 0 12px; font-size: 1rem; line-height: 1.2; }
    h3 { margin: 0 0 8px; font-size: .9rem; line-height: 1.2; }
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
    button.ghost { background: transparent; border-color: transparent; color: var(--muted); }
    button.ghost:hover { color: var(--fg); }
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
    .topbar {
      display: grid;
      grid-template-columns: 1fr minmax(360px, 520px);
      gap: 16px;
      align-items: start;
      margin-bottom: 16px;
    }
    .panel {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 16px;
      margin-bottom: 16px;
    }
    .panel.hidden { display: none; }
    .row { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 10px; }
    .row.with-button { grid-template-columns: 1fr auto; align-items: end; }
    .pill {
      display: inline-block;
      background: var(--codebg);
      color: var(--muted);
      padding: 2px 8px;
      border-radius: 999px;
      font-size: .78rem;
      margin-right: 4px;
    }
    .pill.role-owner { background: rgba(37, 99, 235, .12); color: var(--accent); }
    .pill.role-editor { background: rgba(6, 118, 71, .12); color: var(--ok); }
    .pill.role-viewer { background: rgba(102, 112, 133, .12); color: var(--muted); }
    .notice {
      padding: 9px 12px;
      border-radius: 8px;
      margin-bottom: 12px;
      font-size: .88rem;
    }
    .notice.ok { background: rgba(6, 118, 71, .1); color: var(--ok); }
    .notice.err { background: rgba(180, 35, 24, .1); color: var(--danger); }
    .notice.warn { background: rgba(181, 71, 8, .1); color: var(--warn); }
    .muted { color: var(--muted); }
    .small { font-size: .82rem; }
    .stack > * + * { margin-top: 10px; }
    .actions { display: flex; gap: 6px; flex-wrap: wrap; }
    .switcher { display: flex; gap: 8px; align-items: center; }
    .switcher select { min-width: 220px; }
    .empty-hint {
      text-align: center;
      color: var(--muted);
      padding: 32px 16px;
    }
    .tabs {
      display: flex;
      gap: 6px;
      flex-wrap: wrap;
      border-bottom: 1px solid var(--border);
      margin-bottom: 14px;
    }
    .tab-btn {
      background: transparent;
      border: none;
      border-bottom: 2px solid transparent;
      padding: 8px 14px;
      cursor: pointer;
      color: var(--muted);
      font-weight: 500;
    }
    .tab-btn[aria-selected="true"] {
      color: var(--accent);
      border-bottom-color: var(--accent);
    }
    .tab-btn:disabled { opacity: .4; cursor: not-allowed; }
    dialog {
      width: min(640px, calc(100vw - 32px));
      border: 1px solid var(--border);
      border-radius: 12px;
      background: var(--panel);
      color: var(--fg);
      padding: 0;
    }
    dialog::backdrop { background: rgba(15, 23, 42, .45); }
    dialog form { padding: 16px; }
    .secret-box {
      background: var(--codebg);
      padding: 10px 12px;
      border-radius: 8px;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: .85rem;
      word-break: break-all;
    }
    @media (prefers-color-scheme: dark) {
      :root {
        --bg: #0b1220;
        --fg: #e5e7eb;
        --muted: #9ca3af;
        --panel: #111827;
        --border: #374151;
        --accent: #60a5fa;
        --accent-strong: #3b82f6;
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
  <div class="shell">
    <header class="topbar">
      <div>
        <h1>🌈 Prism · 团队知识库</h1>
        <p class="muted small" style="margin: 6px 0 0;">
          供团队成员使用的轻量入口：用邀请码加入团队，或粘贴已有团队令牌直连。
          所有 token 仅保存在本浏览器的 localStorage，从不上传服务器。
        </p>
      </div>
      <div class="panel" style="margin: 0;">
        <h3>当前团队</h3>
        <div class="switcher">
          <select id="teamSwitcher" aria-label="切换团队">
            <option value="">（未加入任何团队）</option>
          </select>
          <button type="button" id="logoutBtn" class="ghost" title="移除当前团队（不影响服务器数据）">退出</button>
        </div>
        <p id="activeTeamMeta" class="muted small" style="margin: 8px 0 0;"></p>
      </div>
    </header>

    <div id="notice"></div>

    <!-- 未加入任何团队：欢迎/加入面板 -->
    <section id="onboardPanel" class="panel hidden">
      <h2>加入团队</h2>
      <p class="muted small">使用团队负责人发给你的邀请码 (<code>inv_xxx</code>) 加入一个新团队；
        或如果你已经有一个团队令牌 (<code>team_xxx</code>)，可以直接绑定。</p>

      <div class="stack" style="margin-top: 12px;">
        <div>
          <h3>方式 A · 邀请码加入</h3>
          <div class="row">
            <div>
              <label for="joinCode">邀请码</label>
              <input id="joinCode" type="text" placeholder="inv_xxxxx" autocomplete="off">
            </div>
            <div>
              <label for="joinDisplayName">展示名</label>
              <input id="joinDisplayName" type="text" placeholder="例如：张三" autocomplete="off">
            </div>
          </div>
          <div class="actions" style="margin-top: 10px;">
            <button type="button" class="primary" id="joinBtn">加入团队</button>
          </div>
        </div>

        <hr style="border: 0; border-top: 1px solid var(--border); margin: 10px 0;">

        <div>
          <h3>方式 B · 已有令牌直连</h3>
          <div class="row">
            <div>
              <label for="bindSlug">团队 slug</label>
              <input id="bindSlug" type="text" placeholder="例如：platform" autocomplete="off">
            </div>
            <div>
              <label for="bindToken">团队令牌</label>
              <input id="bindToken" type="text" placeholder="team_xxx..." autocomplete="off">
            </div>
            <div>
              <label for="bindRole">我的角色（用于决定显隐 owner-only 入口）</label>
              <select id="bindRole">
                <option value="viewer">viewer（只读）</option>
                <option value="editor" selected>editor（可读写自己的词条）</option>
                <option value="owner">owner（团队负责人）</option>
              </select>
            </div>
          </div>
          <div class="actions" style="margin-top: 10px;">
            <button type="button" id="bindBtn">绑定令牌</button>
          </div>
          <p class="muted small" style="margin-top: 6px;">
            选错角色不会越权 — 真实权限以服务器为准；此项只决定本页是否展示成员/邀请等 owner 专属入口。
          </p>
        </div>
      </div>
    </section>

    <!-- 已加入团队：工作面板（词条/检索/成员/邀请） -->
    <section id="workPanel" class="panel hidden">
      <div class="tabs" role="tablist">
        <button type="button" class="tab-btn" role="tab" data-tab="entries" aria-selected="true">词条</button>
        <button type="button" class="tab-btn" role="tab" data-tab="search" aria-selected="false">检索 / QA</button>
        <button type="button" class="tab-btn" role="tab" data-tab="members" aria-selected="false" data-owner-only="1">成员</button>
        <button type="button" class="tab-btn" role="tab" data-tab="invites" aria-selected="false" data-owner-only="1">邀请</button>
        <span style="flex: 1;"></span>
        <button type="button" class="ghost" id="joinAnotherBtn" title="再加入一个团队">+ 加入另一个团队</button>
      </div>

      <div class="tab-panel" data-tab-panel="entries">
        <div class="stack">
          <div>
            <h3 style="margin: 0 0 8px;">筛选</h3>
            <div class="row">
              <div>
                <label for="entryTagFilter">按标签精确过滤（去 # 自动）</label>
                <input id="entryTagFilter" type="text" placeholder="例如：postgres" autocomplete="off">
              </div>
              <div>
                <label for="entryQueryFilter">正文/标题 substring</label>
                <input id="entryQueryFilter" type="text" placeholder="例如：REINDEX" autocomplete="off">
              </div>
              <div>
                <label for="entryPageSize">每页</label>
                <select id="entryPageSize">
                  <option value="20">20</option>
                  <option value="50" selected>50</option>
                  <option value="100">100</option>
                </select>
              </div>
              <div style="display: flex; align-items: end; gap: 6px;">
                <button type="button" class="primary" id="entryFilterBtn">查询</button>
                <button type="button" id="entryResetBtn">清空</button>
              </div>
            </div>
          </div>

          <div>
            <h3 style="margin: 0 0 8px;">新建词条</h3>
            <div class="stack">
              <div>
                <label for="entryNewTitle">标题</label>
                <input id="entryNewTitle" type="text" placeholder="例如：数据库迁移手册" autocomplete="off">
              </div>
              <div>
                <label for="entryNewBody">正文（Markdown 友好，最长 50000 字符）</label>
                <textarea id="entryNewBody" placeholder="详细内容..."></textarea>
              </div>
              <div>
                <label for="entryNewTags">标签（空白 / 中英文逗号 / 顿号分隔，自动去 # 与去重）</label>
                <input id="entryNewTags" type="text" placeholder="postgres runbook db" autocomplete="off">
              </div>
              <div class="actions">
                <button type="button" class="primary" id="entryCreateBtn">写入词条</button>
              </div>
            </div>
          </div>

          <div>
            <div style="display: flex; align-items: baseline; gap: 12px;">
              <h3 style="margin: 0;">词条列表</h3>
              <span id="entryListMeta" class="muted small"></span>
              <span style="flex: 1;"></span>
              <button type="button" class="ghost" id="entryPrevBtn">← 上一页</button>
              <button type="button" class="ghost" id="entryNextBtn">下一页 →</button>
            </div>
            <table style="margin-top: 8px;">
              <colgroup>
                <col style="width: 26%;">
                <col style="width: 22%;">
                <col style="width: 14%;">
                <col style="width: 14%;">
                <col style="width: 24%;">
              </colgroup>
              <thead>
                <tr>
                  <th>标题</th>
                  <th>标签</th>
                  <th>作者</th>
                  <th>更新时间</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody id="entryListBody">
                <tr><td colspan="5" class="empty-hint">尚未加载</td></tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
      <div class="tab-panel hidden" data-tab-panel="search">
        <div class="stack">
          <div>
            <h3 style="margin: 0 0 8px;">检索 / 拼装 RAG 超级 Prompt</h3>
            <p class="muted small" style="margin: 0;">
              语义模式需要部署侧配置了嵌入服务 (<code>SILICONFLOW_API_KEY</code>)；未配置时自动降级为
              substring + 标签精准召回，前端无感。
            </p>
          </div>

          <div class="row">
            <div>
              <label for="searchQuery">问题 / 查询</label>
              <input id="searchQuery" type="text" placeholder="例如：Postgres 升级到 16 应该注意什么" autocomplete="off">
            </div>
            <div>
              <label for="searchTag">限定标签（可选，全词后过滤）</label>
              <input id="searchTag" type="text" placeholder="例如：db" autocomplete="off">
            </div>
            <div>
              <label for="searchTopK">召回条数 (top_k)</label>
              <input id="searchTopK" type="number" value="5" min="1" max="50">
            </div>
            <div style="display: flex; align-items: end;">
              <label style="display: flex; align-items: center; gap: 6px; margin: 0;">
                <input id="searchUseVector" type="checkbox" checked style="width: auto;">
                <span>启用向量语义检索（未配置嵌入会自动降级）</span>
              </label>
            </div>
          </div>

          <div class="actions">
            <button type="button" class="primary" id="searchRunBtn">检索</button>
            <button type="button" id="promptRunBtn">生成超级 Prompt</button>
          </div>

          <div>
            <h3 style="margin: 0 0 8px;">检索结果</h3>
            <p id="searchMeta" class="muted small" style="margin: 0 0 8px;"></p>
            <div id="searchHitsContainer">
              <p class="empty-hint">尚未检索</p>
            </div>
          </div>

          <div id="promptResultWrap" class="hidden">
            <div style="display: flex; align-items: center; gap: 8px;">
              <h3 style="margin: 0;">拼装结果</h3>
              <span id="promptResultMeta" class="muted small"></span>
              <span style="flex: 1;"></span>
              <button type="button" class="primary" id="promptCopyBtn">复制完整 Prompt</button>
            </div>
            <pre id="promptResultText" style="margin-top: 8px;"></pre>
            <div style="margin-top: 6px;">
              <details>
                <summary class="muted small" style="cursor: pointer;">展开自定义系统提示</summary>
                <textarea id="promptSystem" placeholder="可选：覆盖默认 system_prompt，例如：你是 SRE 助手，回答必须引用知识库 UID。" style="margin-top: 6px;"></textarea>
              </details>
            </div>
          </div>
        </div>
      </div>
      <div class="tab-panel hidden" data-tab-panel="members">
        <div class="stack">
          <div style="display: flex; align-items: baseline; gap: 12px;">
            <h3 style="margin: 0;">团队成员</h3>
            <span id="memberListMeta" class="muted small"></span>
            <span style="flex: 1;"></span>
            <button type="button" id="memberRefreshBtn">刷新</button>
          </div>
          <p class="muted small" style="margin: 0;">
            「最后 owner 保护」：当团队只剩 1 个 owner 时，无法对其降级或移除；
            交接姿势是先升级接班人为 owner，再调整旧 owner。
          </p>
          <table>
            <colgroup>
              <col style="width: 30%;">
              <col style="width: 18%;">
              <col style="width: 22%;">
              <col style="width: 22%;">
              <col style="width: 8%;">
            </colgroup>
            <thead>
              <tr>
                <th>展示名</th>
                <th>角色</th>
                <th>加入时间</th>
                <th>最近活跃</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody id="memberListBody">
              <tr><td colspan="5" class="empty-hint">尚未加载</td></tr>
            </tbody>
          </table>
        </div>
      </div>
      <div class="tab-panel hidden" data-tab-panel="invites">
        <div class="stack">
          <div>
            <h3 style="margin: 0 0 8px;">新建邀请</h3>
            <div class="row">
              <div>
                <label for="inviteNewRole">颁发角色</label>
                <select id="inviteNewRole">
                  <option value="viewer">viewer（只读）</option>
                  <option value="editor" selected>editor（可读写自己的词条）</option>
                  <option value="owner">owner（团队负责人）</option>
                </select>
              </div>
              <div>
                <label for="inviteNewMaxUses">最大使用次数（0 = 无限）</label>
                <input id="inviteNewMaxUses" type="number" value="1" min="0" max="1000">
              </div>
              <div>
                <label for="inviteNewExpiresAt">过期时间（ISO-8601，可空）</label>
                <input id="inviteNewExpiresAt" type="text" placeholder="2026-06-30T23:59:59+08:00" autocomplete="off">
              </div>
              <div style="display: flex; align-items: end;">
                <button type="button" class="primary" id="inviteCreateBtn">生成邀请码</button>
              </div>
            </div>
          </div>

          <div>
            <div style="display: flex; align-items: baseline; gap: 12px;">
              <h3 style="margin: 0;">已发邀请</h3>
              <span id="inviteListMeta" class="muted small"></span>
              <span style="flex: 1;"></span>
              <button type="button" id="inviteRefreshBtn">刷新</button>
            </div>
            <table style="margin-top: 8px;">
              <colgroup>
                <col style="width: 30%;">
                <col style="width: 12%;">
                <col style="width: 14%;">
                <col style="width: 22%;">
                <col style="width: 14%;">
                <col style="width: 8%;">
              </colgroup>
              <thead>
                <tr>
                  <th>邀请码</th>
                  <th>角色</th>
                  <th>使用 / 上限</th>
                  <th>过期时间</th>
                  <th>状态</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody id="inviteListBody">
                <tr><td colspan="6" class="empty-hint">尚未加载</td></tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </section>
  </div>

  <!-- 加入新团队时复用的对话框（已有团队上下文中重新加入） -->
  <dialog id="joinDialog">
    <form method="dialog" class="stack">
      <h3 style="margin: 0;">加入另一个团队</h3>
      <div>
        <label for="dlgJoinCode">邀请码</label>
        <input id="dlgJoinCode" type="text" placeholder="inv_xxxxx" autocomplete="off" required>
      </div>
      <div>
        <label for="dlgJoinDisplayName">展示名</label>
        <input id="dlgJoinDisplayName" type="text" placeholder="例如：张三" autocomplete="off" required>
      </div>
      <div class="actions" style="justify-content: flex-end;">
        <button type="button" value="cancel" data-close-dialog="joinDialog">取消</button>
        <button type="button" class="primary" id="dlgJoinSubmit">加入</button>
      </div>
    </form>
  </dialog>

  <!-- 编辑词条对话框 -->
  <dialog id="entryEditDialog">
    <form method="dialog" class="stack">
      <h3 style="margin: 0;">编辑词条</h3>
      <p class="muted small" id="entryEditMeta" style="margin: 0;"></p>
      <input type="hidden" id="entryEditUid">
      <div>
        <label for="entryEditTitle">标题</label>
        <input id="entryEditTitle" type="text" autocomplete="off">
      </div>
      <div>
        <label for="entryEditBody">正文</label>
        <textarea id="entryEditBody" style="min-height: 200px;"></textarea>
      </div>
      <div>
        <label for="entryEditTags">标签（空白 / 中英文逗号 / 顿号分隔）</label>
        <input id="entryEditTags" type="text" autocomplete="off">
      </div>
      <div class="actions" style="justify-content: flex-end;">
        <button type="button" value="cancel" data-close-dialog="entryEditDialog">取消</button>
        <button type="button" class="primary" id="entryEditSubmit">保存</button>
      </div>
    </form>
  </dialog>

  <!-- 新邀请码一次性展示 -->
  <dialog id="inviteRevealDialog">
    <form method="dialog" class="stack">
      <h3 style="margin: 0;">邀请码已生成</h3>
      <p class="muted small" style="margin: 0;">
        请<strong>立刻</strong>把下面的邀请码通过<strong>安全渠道</strong>（不是公共群）
        发给被邀请人。此邀请码不会再次显示。
      </p>
      <div class="secret-box" id="inviteRevealCode"></div>
      <p id="inviteRevealMeta" class="muted small" style="margin: 0;"></p>
      <div class="actions" style="justify-content: flex-end;">
        <button type="button" class="primary" id="inviteRevealCopyBtn">复制邀请码</button>
        <button type="button" value="cancel" data-close-dialog="inviteRevealDialog">关闭</button>
      </div>
    </form>
  </dialog>

  <script>
  // ---------- 多团队 localStorage 管理 ----------
  const STORAGE_TOKENS = "memosima.teams.tokens";
  const STORAGE_ACTIVE = "memosima.teams.active";

  function loadTeamMap() {
    try {
      const raw = localStorage.getItem(STORAGE_TOKENS);
      if (!raw) return {};
      const parsed = JSON.parse(raw);
      return (parsed && typeof parsed === "object") ? parsed : {};
    } catch (e) {
      console.warn("loadTeamMap failed:", e);
      return {};
    }
  }

  function saveTeamMap(map) {
    localStorage.setItem(STORAGE_TOKENS, JSON.stringify(map || {}));
  }

  function getActiveSlug() {
    return localStorage.getItem(STORAGE_ACTIVE) || "";
  }

  function setActiveSlug(slug) {
    if (slug) {
      localStorage.setItem(STORAGE_ACTIVE, slug);
    } else {
      localStorage.removeItem(STORAGE_ACTIVE);
    }
  }

  function rememberTeam({ slug, token, displayName, teamName, role }) {
    const map = loadTeamMap();
    map[slug] = {
      token,
      displayName: displayName || "",
      teamName: teamName || slug,
      role: role || "viewer",
      joinedAt: new Date().toISOString(),
    };
    saveTeamMap(map);
    setActiveSlug(slug);
  }

  function forgetTeam(slug) {
    const map = loadTeamMap();
    delete map[slug];
    saveTeamMap(map);
    if (getActiveSlug() === slug) {
      const keys = Object.keys(map);
      setActiveSlug(keys.length ? keys[0] : "");
    }
  }

  function getActiveTeam() {
    const slug = getActiveSlug();
    if (!slug) return null;
    const map = loadTeamMap();
    const team = map[slug];
    return team ? { slug, ...team } : null;
  }

  // ---------- 通用网络层 ----------
  async function requestJson(method, path, body) {
    const headers = new Headers();
    if (body !== undefined) {
      headers.set("Content-Type", "application/json");
    }
    // /teams/join 是公开接口，其它 /teams/{slug}/... 需要当前团队 token
    if (path.startsWith("/teams/") && path !== "/teams/join") {
      const active = getActiveTeam();
      if (!active) throw new Error("当前未选中任何团队");
      headers.set("Authorization", `Bearer ${active.token}`);
    }
    const init = { method, headers };
    if (body !== undefined) init.body = JSON.stringify(body);
    const resp = await fetch(path, init);
    const text = await resp.text();
    let data = null;
    if (text) {
      try { data = JSON.parse(text); } catch (e) { data = { raw: text }; }
    }
    if (!resp.ok) {
      const detail = (data && (data.detail || data.message)) || resp.statusText || `HTTP ${resp.status}`;
      const err = new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
      err.status = resp.status;
      err.payload = data;
      throw err;
    }
    return data;
  }

  // ---------- 通知 ----------
  function showNotice(kind, text, timeoutMs) {
    const el = document.getElementById("notice");
    el.innerHTML = `<div class="notice ${kind}">${escapeHtml(text)}</div>`;
    if (timeoutMs && timeoutMs > 0) {
      setTimeout(() => {
        if (el.textContent.includes(text)) el.innerHTML = "";
      }, timeoutMs);
    }
  }

  function escapeHtml(text) {
    return String(text == null ? "" : text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  // ---------- 界面渲染 ----------
  function renderSwitcher() {
    const map = loadTeamMap();
    const slugs = Object.keys(map).sort();
    const select = document.getElementById("teamSwitcher");
    const activeSlug = getActiveSlug();

    if (!slugs.length) {
      select.innerHTML = `<option value="">（未加入任何团队）</option>`;
      document.getElementById("logoutBtn").disabled = true;
    } else {
      select.innerHTML = slugs.map(slug => {
        const team = map[slug];
        const label = `${team.teamName || slug}（${slug}） · ${team.role}`;
        const selected = slug === activeSlug ? " selected" : "";
        return `<option value="${escapeHtml(slug)}"${selected}>${escapeHtml(label)}</option>`;
      }).join("");
      document.getElementById("logoutBtn").disabled = false;
    }

    const active = getActiveTeam();
    const meta = document.getElementById("activeTeamMeta");
    if (active) {
      meta.textContent = `身份：${active.displayName || "（未命名）"} · 角色：${active.role} · 加入时间：${new Date(active.joinedAt).toLocaleString()}`;
    } else {
      meta.textContent = "";
    }

    const hasTeam = !!active;
    document.getElementById("onboardPanel").classList.toggle("hidden", hasTeam);
    document.getElementById("workPanel").classList.toggle("hidden", !hasTeam);

    // 根据角色显隐 owner-only tab
    const ownerOnly = active && active.role === "owner";
    document.querySelectorAll('[data-owner-only="1"]').forEach(btn => {
      btn.style.display = ownerOnly ? "" : "none";
    });

    // 切到「有团队」状态时，自动 reload 一次词条列表（如果当前 tab 是 entries）
    if (hasTeam) {
      const selectedTab = document.querySelector('.tab-btn[aria-selected="true"]');
      const tabName = selectedTab ? selectedTab.dataset.tab : "entries";
      if (tabName === "entries") {
        entryState.offset = 0;
        loadEntries().catch(e => console.warn("auto loadEntries failed:", e));
      }
    }
  }

  function switchTab(tab) {
    document.querySelectorAll(".tab-btn").forEach(btn => {
      btn.setAttribute("aria-selected", String(btn.dataset.tab === tab));
    });
    document.querySelectorAll("[data-tab-panel]").forEach(panel => {
      panel.classList.toggle("hidden", panel.dataset.tabPanel !== tab);
    });
    // 切到对应 tab 时按需 reload
    if (tab === "entries") {
      loadEntries().catch(e => showNotice("err", `加载词条失败：${e.message}`, 6000));
    } else if (tab === "members") {
      loadMembers().catch(e => showNotice("err", `加载成员失败：${e.message}`, 6000));
    } else if (tab === "invites") {
      loadInvites().catch(e => showNotice("err", `加载邀请失败：${e.message}`, 6000));
    }
  }

  // ---------- 词条 CRUD ----------
  const entryState = {
    tag: "",
    query: "",
    limit: 50,
    offset: 0,
    total: 0,
  };

  function parseTags(input) {
    if (!input) return [];
    return String(input)
      .split(/[\\s,，、]+/)
      .map(t => t.trim().replace(/^#+/, ""))
      .filter(Boolean);
  }

  function truncate(text, max) {
    const flat = String(text || "").replace(/\\s+/g, " ").trim();
    if (flat.length <= max) return flat;
    return flat.slice(0, max - 1) + "…";
  }

  function renderTagPills(tags) {
    if (!tags || !tags.length) return '<span class="muted small">—</span>';
    return tags.map(t => `<span class="pill">#${escapeHtml(t)}</span>`).join("");
  }

  function formatDateTime(s) {
    if (!s) return "—";
    try {
      const d = new Date(s);
      if (Number.isNaN(d.getTime())) return s;
      return d.toLocaleString();
    } catch (e) {
      return s;
    }
  }

  async function loadEntries() {
    const active = getActiveTeam();
    if (!active) return;
    const tbody = document.getElementById("entryListBody");
    tbody.innerHTML = `<tr><td colspan="5" class="empty-hint">加载中…</td></tr>`;
    const params = new URLSearchParams();
    params.set("limit", String(entryState.limit));
    params.set("offset", String(entryState.offset));
    if (entryState.tag) params.set("tag", entryState.tag);
    if (entryState.query) params.set("query", entryState.query);
    const path = `/teams/${encodeURIComponent(active.slug)}/entries?${params.toString()}`;
    const data = await requestJson("GET", path);
    const entries = (data && data.entries) || [];
    entryState.total = (data && typeof data.total === "number") ? data.total : entries.length;

    const meta = document.getElementById("entryListMeta");
    const from = entries.length ? entryState.offset + 1 : 0;
    const to = entryState.offset + entries.length;
    meta.textContent = `共 ${entryState.total} 条，当前 ${from}–${to}`;

    document.getElementById("entryPrevBtn").disabled = entryState.offset <= 0;
    document.getElementById("entryNextBtn").disabled = entryState.offset + entries.length >= entryState.total;

    if (!entries.length) {
      tbody.innerHTML = `<tr><td colspan="5" class="empty-hint">没有匹配的词条</td></tr>`;
      return;
    }
    tbody.innerHTML = entries.map(entry => `
      <tr data-entry-uid="${escapeHtml(entry.uid)}">
        <td><strong>${escapeHtml(entry.title || "（无标题）")}</strong>
          <div class="muted small" style="margin-top: 4px;">${escapeHtml(truncate(entry.body, 120))}</div>
        </td>
        <td>${renderTagPills(entry.tags)}</td>
        <td class="small">${escapeHtml(entry.author_display_name || "—")}</td>
        <td class="small">${escapeHtml(formatDateTime(entry.updated_at))}</td>
        <td>
          <div class="actions">
            <button type="button" data-action="edit-entry" data-uid="${escapeHtml(entry.uid)}">编辑</button>
            <button type="button" class="danger" data-action="delete-entry" data-uid="${escapeHtml(entry.uid)}">删除</button>
          </div>
        </td>
      </tr>
    `).join("");
  }

  async function createEntryAction() {
    const active = getActiveTeam();
    if (!active) return;
    const title = document.getElementById("entryNewTitle").value.trim();
    const body = document.getElementById("entryNewBody").value.trim();
    const tags = parseTags(document.getElementById("entryNewTags").value);
    if (!body) {
      showNotice("err", "正文必填", 4000);
      return;
    }
    await requestJson("POST", `/teams/${encodeURIComponent(active.slug)}/entries`, { title, body, tags });
    document.getElementById("entryNewTitle").value = "";
    document.getElementById("entryNewBody").value = "";
    document.getElementById("entryNewTags").value = "";
    showNotice("ok", "已写入词条", 3000);
    entryState.offset = 0;
    await loadEntries();
  }

  async function openEditEntry(uid) {
    const active = getActiveTeam();
    if (!active) return;
    const data = await requestJson("GET", `/teams/${encodeURIComponent(active.slug)}/entries/${encodeURIComponent(uid)}`);
    document.getElementById("entryEditUid").value = data.uid;
    document.getElementById("entryEditTitle").value = data.title || "";
    document.getElementById("entryEditBody").value = data.body || "";
    document.getElementById("entryEditTags").value = (data.tags || []).map(t => `#${t}`).join(" ");
    document.getElementById("entryEditMeta").textContent =
      `UID: ${data.uid} · 作者：${data.author_display_name || "—"} · 创建：${formatDateTime(data.created_at)}`;
    document.getElementById("entryEditDialog").showModal();
  }

  async function submitEditEntry() {
    const active = getActiveTeam();
    if (!active) return;
    const uid = document.getElementById("entryEditUid").value;
    const payload = {
      title: document.getElementById("entryEditTitle").value,
      body: document.getElementById("entryEditBody").value,
      tags: parseTags(document.getElementById("entryEditTags").value),
    };
    await requestJson("PUT", `/teams/${encodeURIComponent(active.slug)}/entries/${encodeURIComponent(uid)}`, payload);
    document.getElementById("entryEditDialog").close();
    showNotice("ok", "已保存", 3000);
    await loadEntries();
  }

  async function deleteEntryAction(uid) {
    const active = getActiveTeam();
    if (!active) return;
    if (!confirm(`确定删除词条 ${uid}？此操作不可撤销。`)) return;
    await requestJson("DELETE", `/teams/${encodeURIComponent(active.slug)}/entries/${encodeURIComponent(uid)}`);
    showNotice("ok", "已删除", 3000);
    // 如果当前页删空了，回到上一页
    const remaining = entryState.total - 1;
    if (remaining > 0 && entryState.offset >= remaining) {
      entryState.offset = Math.max(0, entryState.offset - entryState.limit);
    }
    await loadEntries();
  }

  // ---------- 检索 / QA ----------
  function getSearchPayload(extra) {
    const query = document.getElementById("searchQuery").value.trim();
    if (!query) throw new Error("查询不能为空");
    const tag = document.getElementById("searchTag").value.trim().replace(/^#+/, "");
    const topK = Math.max(1, Math.min(50, parseInt(document.getElementById("searchTopK").value, 10) || 5));
    const useVector = document.getElementById("searchUseVector").checked;
    const payload = { query, top_k: topK, use_vector: useVector };
    if (tag) payload.tag = tag;
    return Object.assign(payload, extra || {});
  }

  async function runSearch() {
    const active = getActiveTeam();
    if (!active) return;
    const payload = getSearchPayload();
    document.getElementById("searchMeta").textContent = "检索中…";
    document.getElementById("searchHitsContainer").innerHTML = `<p class="empty-hint">检索中…</p>`;
    const data = await requestJson("POST", `/teams/${encodeURIComponent(active.slug)}/search`, payload);
    const hits = (data && data.hits) || [];
    const mode = data && data.retrieval_mode;
    const modeLabel = mode === "vector" ? "🧠 向量语义" :
                      mode === "text" ? "🔍 文本/标签" :
                      mode || "—";
    document.getElementById("searchMeta").textContent =
      `召回 ${hits.length} 条 · 模式：${modeLabel}`;
    if (!hits.length) {
      document.getElementById("searchHitsContainer").innerHTML =
        `<p class="empty-hint">未命中任何词条；试试取消「向量」勾选 或 拆解为关键词后再查</p>`;
      return;
    }
    document.getElementById("searchHitsContainer").innerHTML = hits.map((hit, idx) => {
      const e = hit.entry || {};
      return `
        <div class="panel" style="margin-bottom: 10px;">
          <div style="display: flex; align-items: baseline; gap: 8px;">
            <strong>#${idx + 1} · ${escapeHtml(e.title || "（无标题）")}</strong>
            <span class="muted small">score=${Number(hit.score || 0).toFixed(3)}</span>
            <span style="flex: 1;"></span>
            <span class="muted small">${escapeHtml(e.author_display_name || "—")}</span>
            <span class="muted small">${escapeHtml(formatDateTime(e.updated_at))}</span>
          </div>
          <div style="margin-top: 6px;">${renderTagPills(e.tags)}</div>
          <div class="small muted" style="margin-top: 6px;">UID: ${escapeHtml(e.uid)}</div>
          ${hit.snippet ? `<pre style="margin-top: 8px; max-height: 180px;">${escapeHtml(hit.snippet)}</pre>` : ""}
        </div>`;
    }).join("");
  }

  async function runPrompt() {
    const active = getActiveTeam();
    if (!active) return;
    const system = document.getElementById("promptSystem").value.trim();
    const payload = getSearchPayload(system ? { system_prompt: system } : {});
    document.getElementById("promptResultWrap").classList.remove("hidden");
    document.getElementById("promptResultText").textContent = "生成中…";
    document.getElementById("promptResultMeta").textContent = "";
    const data = await requestJson(
      "POST",
      `/teams/${encodeURIComponent(active.slug)}/qa/generate-prompt`,
      payload,
    );
    const mode = data && data.retrieval_mode;
    const modeLabel = mode === "vector" ? "🧠 向量语义" :
                      mode === "text" ? "🔍 文本/标签" :
                      mode || "—";
    document.getElementById("promptResultMeta").textContent =
      `引用 ${data && data.retrieved_count} 条 · 模式：${modeLabel}`;
    document.getElementById("promptResultText").textContent = (data && data.assembled_prompt) || "";
  }

  async function copyPromptAction() {
    const text = document.getElementById("promptResultText").textContent;
    if (!text) {
      showNotice("warn", "尚无可复制内容", 3000);
      return;
    }
    try {
      await navigator.clipboard.writeText(text);
      showNotice("ok", "已复制 Prompt 到剪贴板", 3000);
    } catch (e) {
      // 兜底：手动选区
      const range = document.createRange();
      range.selectNodeContents(document.getElementById("promptResultText"));
      const sel = window.getSelection();
      sel.removeAllRanges();
      sel.addRange(range);
      showNotice("warn", `自动复制失败，已为你选中文本，请手动 Ctrl+C：${e.message}`, 6000);
    }
  }

  async function copyTextToClipboard(text, okMsg) {
    try {
      await navigator.clipboard.writeText(text);
      if (okMsg) showNotice("ok", okMsg, 3000);
      return true;
    } catch (e) {
      showNotice("warn", `复制失败：${e.message}`, 5000);
      return false;
    }
  }

  // ---------- 成员管理（owner 专属）----------
  function rolePill(role) {
    const cls = role === "owner" ? "role-owner" : role === "editor" ? "role-editor" : "role-viewer";
    return `<span class="pill ${cls}">${escapeHtml(role)}</span>`;
  }

  async function loadMembers() {
    const active = getActiveTeam();
    if (!active) return;
    const tbody = document.getElementById("memberListBody");
    tbody.innerHTML = `<tr><td colspan="5" class="empty-hint">加载中…</td></tr>`;
    const data = await requestJson("GET", `/teams/${encodeURIComponent(active.slug)}/members`);
    const members = (data && data.members) || [];
    document.getElementById("memberListMeta").textContent = `共 ${members.length} 名成员`;
    if (!members.length) {
      tbody.innerHTML = `<tr><td colspan="5" class="empty-hint">尚无成员</td></tr>`;
      return;
    }
    tbody.innerHTML = members.map(m => `
      <tr data-member-id="${m.id}">
        <td><strong>${escapeHtml(m.display_name || "（未命名）")}</strong>
          <div class="muted small" style="margin-top: 2px;">ID #${m.id}</div>
        </td>
        <td>
          <select data-action="change-role" data-member-id="${m.id}">
            ${["owner","editor","viewer"].map(r =>
              `<option value="${r}"${r === m.role ? " selected" : ""}>${r}</option>`
            ).join("")}
          </select>
        </td>
        <td class="small">${escapeHtml(formatDateTime(m.created_at))}</td>
        <td class="small">${escapeHtml(formatDateTime(m.last_active_at))}</td>
        <td>
          <button type="button" class="danger" data-action="remove-member" data-member-id="${m.id}">移除</button>
        </td>
      </tr>
    `).join("");
  }

  async function changeMemberRole(memberId, role, selectEl) {
    const active = getActiveTeam();
    if (!active) return;
    try {
      await requestJson("PUT", `/teams/${encodeURIComponent(active.slug)}/members/${memberId}/role`, { role });
      showNotice("ok", `已更新成员 #${memberId} 的角色为 ${role}`, 3000);
      await loadMembers();
    } catch (e) {
      showNotice("err", `角色调整失败：${e.message}`, 6000);
      // 回滚 select 的展示值
      if (selectEl) {
        await loadMembers().catch(() => {});
      }
    }
  }

  async function removeMember(memberId) {
    const active = getActiveTeam();
    if (!active) return;
    if (!confirm(`确定移除成员 #${memberId}？\\n移除后其 token 立即失效，但 ta 写过的词条不会被自动删除。`)) {
      return;
    }
    try {
      await requestJson("DELETE", `/teams/${encodeURIComponent(active.slug)}/members/${memberId}`);
      showNotice("ok", `已移除成员 #${memberId}`, 3000);
      await loadMembers();
    } catch (e) {
      showNotice("err", `移除失败：${e.message}`, 6000);
    }
  }

  // ---------- 邀请管理（owner 专属）----------
  function inviteStatusLabel(inv) {
    if (inv.revoked_at) return `<span class="pill" style="color: var(--danger);">已撤销</span>`;
    if (inv.expires_at && new Date(inv.expires_at).getTime() < Date.now()) {
      return `<span class="pill" style="color: var(--warn);">已过期</span>`;
    }
    if (inv.max_uses > 0 && inv.uses >= inv.max_uses) {
      return `<span class="pill" style="color: var(--muted);">已耗尽</span>`;
    }
    return `<span class="pill" style="color: var(--ok);">可用</span>`;
  }

  async function loadInvites() {
    const active = getActiveTeam();
    if (!active) return;
    const tbody = document.getElementById("inviteListBody");
    tbody.innerHTML = `<tr><td colspan="6" class="empty-hint">加载中…</td></tr>`;
    const data = await requestJson("GET", `/teams/${encodeURIComponent(active.slug)}/invites`);
    const invites = (data && data.invites) || [];
    document.getElementById("inviteListMeta").textContent = `共 ${invites.length} 条邀请记录`;
    if (!invites.length) {
      tbody.innerHTML = `<tr><td colspan="6" class="empty-hint">尚未发出任何邀请</td></tr>`;
      return;
    }
    tbody.innerHTML = invites.map(inv => `
      <tr data-invite-id="${inv.id}">
        <td>
          <code style="font-size: .85rem; word-break: break-all;">${escapeHtml(inv.code)}</code>
          <div class="muted small" style="margin-top: 2px;">创建：${escapeHtml(formatDateTime(inv.created_at))}</div>
        </td>
        <td>${rolePill(inv.role)}</td>
        <td class="small">${inv.uses} / ${inv.max_uses === 0 ? "∞" : inv.max_uses}</td>
        <td class="small">${escapeHtml(formatDateTime(inv.expires_at))}</td>
        <td>${inviteStatusLabel(inv)}</td>
        <td>
          <button type="button" class="danger" data-action="revoke-invite" data-invite-id="${inv.id}"${inv.revoked_at ? " disabled" : ""}>撤销</button>
        </td>
      </tr>
    `).join("");
  }

  async function createInviteAction() {
    const active = getActiveTeam();
    if (!active) return;
    const role = document.getElementById("inviteNewRole").value;
    const maxUses = parseInt(document.getElementById("inviteNewMaxUses").value, 10);
    const expiresAt = document.getElementById("inviteNewExpiresAt").value.trim();
    const payload = { role, max_uses: Number.isFinite(maxUses) ? maxUses : 0 };
    if (expiresAt) payload.expires_at = expiresAt;
    const data = await requestJson("POST", `/teams/${encodeURIComponent(active.slug)}/invites`, payload);
    if (!data || !data.code) throw new Error("服务端未返回邀请码");

    document.getElementById("inviteRevealCode").textContent = data.code;
    const meta = [];
    meta.push(`角色：${data.role}`);
    meta.push(`上限：${data.max_uses === 0 ? "无限" : data.max_uses + " 次"}`);
    if (data.expires_at) meta.push(`过期时间：${formatDateTime(data.expires_at)}`);
    document.getElementById("inviteRevealMeta").textContent = meta.join(" · ");
    document.getElementById("inviteRevealDialog").showModal();

    // 清空表单 + 刷新列表
    document.getElementById("inviteNewMaxUses").value = "1";
    document.getElementById("inviteNewExpiresAt").value = "";
    await loadInvites();
  }

  async function revokeInviteAction(inviteId) {
    const active = getActiveTeam();
    if (!active) return;
    if (!confirm(`确定撤销邀请 #${inviteId}？撤销后该邀请码立即作废。`)) return;
    await requestJson("DELETE", `/teams/${encodeURIComponent(active.slug)}/invites/${inviteId}`);
    showNotice("ok", `已撤销邀请 #${inviteId}`, 3000);
    await loadInvites();
  }

  // ---------- 业务动作 ----------
  async function refreshTeamMeta(slug) {
    // GET /teams/{slug} 返回平铺 TeamView：{id, slug, name, description, member_count, ...}
    // 拉取此接口主要用于：(1) 校验 token 仍然有效；(2) 同步最新 teamName
    try {
      const data = await requestJson("GET", `/teams/${encodeURIComponent(slug)}`);
      const map = loadTeamMap();
      if (!map[slug]) return;
      if (data && typeof data.name === "string" && data.name) {
        map[slug].teamName = data.name;
      }
      saveTeamMap(map);
    } catch (e) {
      // token 失效（401/403/404）就清掉这一项；其他错误（比如网络）保留
      if (e.status === 401 || e.status === 403 || e.status === 404) {
        showNotice("warn", `团队 ${slug} 的令牌已失效，已自动移除：${e.message}`, 6000);
        forgetTeam(slug);
      } else {
        console.warn("refreshTeamMeta failed for", slug, e);
      }
    }
  }

  async function joinViaCode(code, displayName) {
    const payload = await requestJson("POST", "/teams/join", {
      code: String(code || "").trim(),
      display_name: String(displayName || "").trim(),
    });
    if (!payload || !payload.token || !payload.team) {
      throw new Error("服务端未返回 token / team");
    }
    const slug = payload.team.slug;
    rememberTeam({
      slug,
      token: payload.token,
      displayName: (payload.member && payload.member.display_name) || displayName,
      teamName: payload.team.name,
      role: (payload.member && payload.member.role) || "viewer",
    });
    return slug;
  }

  async function bindExistingToken(slug, token, role) {
    slug = String(slug || "").trim();
    token = String(token || "").trim();
    role = String(role || "viewer").trim();
    if (!slug || !token) throw new Error("slug 和 token 都不能为空");
    if (!["owner", "editor", "viewer"].includes(role)) role = "viewer";
    // 先把 token 落地，发起一次拉取试试，再决定是否保留
    const map = loadTeamMap();
    map[slug] = {
      token,
      displayName: (map[slug] && map[slug].displayName) || "",
      teamName: (map[slug] && map[slug].teamName) || slug,
      role,
      joinedAt: new Date().toISOString(),
    };
    saveTeamMap(map);
    setActiveSlug(slug);
    await refreshTeamMeta(slug);
    // 如果 refresh 把它清掉了，说明 token 不对
    if (!loadTeamMap()[slug]) {
      throw new Error("令牌校验失败");
    }
  }

  // ---------- 事件绑定 ----------
  document.addEventListener("DOMContentLoaded", () => {
    renderSwitcher();

    // 初始时对每个已存团队后台 refresh 一次
    const map = loadTeamMap();
    Object.keys(map).forEach(slug => { refreshTeamMeta(slug).then(renderSwitcher); });

    document.getElementById("teamSwitcher").addEventListener("change", (e) => {
      const slug = e.target.value;
      if (slug) {
        setActiveSlug(slug);
        renderSwitcher();
      }
    });

    document.getElementById("logoutBtn").addEventListener("click", () => {
      const active = getActiveTeam();
      if (!active) return;
      if (!confirm(`确定移除本浏览器上的 ${active.teamName || active.slug} 团队令牌？\\n服务器上的成员关系不会被删除，可以使用同一邀请码或新邀请码再次加入。`)) {
        return;
      }
      forgetTeam(active.slug);
      renderSwitcher();
      showNotice("ok", `已从浏览器移除 ${active.slug}`, 3000);
    });

    document.getElementById("joinBtn").addEventListener("click", async () => {
      const code = document.getElementById("joinCode").value;
      const name = document.getElementById("joinDisplayName").value;
      if (!code || !name) {
        showNotice("err", "邀请码与展示名均必填", 4000);
        return;
      }
      try {
        const slug = await joinViaCode(code, name);
        renderSwitcher();
        document.getElementById("joinCode").value = "";
        document.getElementById("joinDisplayName").value = "";
        showNotice("ok", `已加入团队 ${slug}`, 4000);
      } catch (e) {
        showNotice("err", `加入失败：${e.message}`, 6000);
      }
    });

    document.getElementById("bindBtn").addEventListener("click", async () => {
      const slug = document.getElementById("bindSlug").value;
      const token = document.getElementById("bindToken").value;
      const role = document.getElementById("bindRole").value;
      try {
        await bindExistingToken(slug, token, role);
        renderSwitcher();
        document.getElementById("bindSlug").value = "";
        document.getElementById("bindToken").value = "";
        showNotice("ok", `已绑定团队 ${slug}`, 4000);
      } catch (e) {
        showNotice("err", `绑定失败：${e.message}`, 6000);
      }
    });

    document.querySelectorAll(".tab-btn").forEach(btn => {
      btn.addEventListener("click", () => switchTab(btn.dataset.tab));
    });

    document.getElementById("joinAnotherBtn").addEventListener("click", () => {
      const dlg = document.getElementById("joinDialog");
      document.getElementById("dlgJoinCode").value = "";
      document.getElementById("dlgJoinDisplayName").value = "";
      dlg.showModal();
    });

    document.querySelectorAll("[data-close-dialog]").forEach(btn => {
      btn.addEventListener("click", () => {
        const dlg = document.getElementById(btn.dataset.closeDialog);
        if (dlg) dlg.close();
      });
    });

    document.getElementById("dlgJoinSubmit").addEventListener("click", async () => {
      const code = document.getElementById("dlgJoinCode").value;
      const name = document.getElementById("dlgJoinDisplayName").value;
      if (!code || !name) {
        showNotice("err", "邀请码与展示名均必填", 4000);
        return;
      }
      try {
        const slug = await joinViaCode(code, name);
        document.getElementById("joinDialog").close();
        renderSwitcher();
        showNotice("ok", `已加入新团队 ${slug}`, 4000);
      } catch (e) {
        showNotice("err", `加入失败：${e.message}`, 6000);
      }
    });

    // ---------- 词条 tab 事件 ----------
    document.getElementById("entryFilterBtn").addEventListener("click", () => {
      entryState.tag = document.getElementById("entryTagFilter").value.trim().replace(/^#+/, "");
      entryState.query = document.getElementById("entryQueryFilter").value.trim();
      entryState.limit = parseInt(document.getElementById("entryPageSize").value, 10) || 50;
      entryState.offset = 0;
      loadEntries().catch(e => showNotice("err", `加载词条失败：${e.message}`, 6000));
    });

    document.getElementById("entryResetBtn").addEventListener("click", () => {
      document.getElementById("entryTagFilter").value = "";
      document.getElementById("entryQueryFilter").value = "";
      entryState.tag = "";
      entryState.query = "";
      entryState.offset = 0;
      loadEntries().catch(e => showNotice("err", `加载词条失败：${e.message}`, 6000));
    });

    document.getElementById("entryPrevBtn").addEventListener("click", () => {
      if (entryState.offset <= 0) return;
      entryState.offset = Math.max(0, entryState.offset - entryState.limit);
      loadEntries().catch(e => showNotice("err", `加载词条失败：${e.message}`, 6000));
    });

    document.getElementById("entryNextBtn").addEventListener("click", () => {
      entryState.offset = entryState.offset + entryState.limit;
      loadEntries().catch(e => showNotice("err", `加载词条失败：${e.message}`, 6000));
    });

    document.getElementById("entryCreateBtn").addEventListener("click", () => {
      createEntryAction().catch(e => showNotice("err", `写入失败：${e.message}`, 6000));
    });

    // 列表里的「编辑 / 删除」按钮：用事件委托
    document.getElementById("entryListBody").addEventListener("click", (e) => {
      const target = e.target.closest("[data-action]");
      if (!target) return;
      const action = target.dataset.action;
      const uid = target.dataset.uid;
      if (action === "edit-entry") {
        openEditEntry(uid).catch(err => showNotice("err", `打开编辑失败：${err.message}`, 6000));
      } else if (action === "delete-entry") {
        deleteEntryAction(uid).catch(err => showNotice("err", `删除失败：${err.message}`, 6000));
      }
    });

    document.getElementById("entryEditSubmit").addEventListener("click", () => {
      submitEditEntry().catch(e => showNotice("err", `保存失败：${e.message}`, 6000));
    });

    // ---------- 检索 / QA tab 事件 ----------
    document.getElementById("searchRunBtn").addEventListener("click", () => {
      runSearch().catch(e => showNotice("err", `检索失败：${e.message}`, 6000));
    });

    document.getElementById("promptRunBtn").addEventListener("click", () => {
      runPrompt().catch(e => showNotice("err", `生成 Prompt 失败：${e.message}`, 6000));
    });

    document.getElementById("promptCopyBtn").addEventListener("click", () => {
      copyPromptAction();
    });

    // 回车快捷键：在 searchQuery 上按 Enter 触发检索
    document.getElementById("searchQuery").addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        document.getElementById("searchRunBtn").click();
      }
    });

    // ---------- 成员 tab 事件 ----------
    document.getElementById("memberRefreshBtn").addEventListener("click", () => {
      loadMembers().catch(e => showNotice("err", `加载成员失败：${e.message}`, 6000));
    });

    // 列表里的「角色 select / 移除」按钮：用事件委托
    document.getElementById("memberListBody").addEventListener("change", (e) => {
      const target = e.target.closest('[data-action="change-role"]');
      if (!target) return;
      const memberId = parseInt(target.dataset.memberId, 10);
      const role = target.value;
      changeMemberRole(memberId, role, target);
    });
    document.getElementById("memberListBody").addEventListener("click", (e) => {
      const target = e.target.closest('[data-action="remove-member"]');
      if (!target) return;
      const memberId = parseInt(target.dataset.memberId, 10);
      removeMember(memberId);
    });

    // ---------- 邀请 tab 事件 ----------
    document.getElementById("inviteRefreshBtn").addEventListener("click", () => {
      loadInvites().catch(e => showNotice("err", `加载邀请失败：${e.message}`, 6000));
    });

    document.getElementById("inviteCreateBtn").addEventListener("click", () => {
      createInviteAction().catch(e => showNotice("err", `生成邀请失败：${e.message}`, 6000));
    });

    document.getElementById("inviteRevealCopyBtn").addEventListener("click", () => {
      const code = document.getElementById("inviteRevealCode").textContent || "";
      copyTextToClipboard(code, "已复制邀请码到剪贴板");
    });

    document.getElementById("inviteListBody").addEventListener("click", (e) => {
      const target = e.target.closest('[data-action="revoke-invite"]');
      if (!target || target.disabled) return;
      const inviteId = parseInt(target.dataset.inviteId, 10);
      revokeInviteAction(inviteId).catch(err => showNotice("err", `撤销失败：${err.message}`, 6000));
    });
  });
  </script>
</body>
</html>
"""
