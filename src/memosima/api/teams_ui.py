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
        <p class="muted small">（词条 CRUD 即将在下一步上线，本骨架已具备团队切换能力。）</p>
      </div>
      <div class="tab-panel hidden" data-tab-panel="search">
        <p class="muted small">（检索 + QA Prompt 即将在下一步上线。）</p>
      </div>
      <div class="tab-panel hidden" data-tab-panel="members">
        <p class="muted small">（成员管理（owner 专属）即将上线。）</p>
      </div>
      <div class="tab-panel hidden" data-tab-panel="invites">
        <p class="muted small">（邀请管理（owner 专属）即将上线。）</p>
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
  }

  function switchTab(tab) {
    document.querySelectorAll(".tab-btn").forEach(btn => {
      btn.setAttribute("aria-selected", String(btn.dataset.tab === tab));
    });
    document.querySelectorAll("[data-tab-panel]").forEach(panel => {
      panel.classList.toggle("hidden", panel.dataset.tabPanel !== tab);
    });
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
  });
  </script>
</body>
</html>
"""
