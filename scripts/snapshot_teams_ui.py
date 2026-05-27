"""自动化截图脚本：起本地 sidecar → 造 demo 数据 → headless 截 /admin/ui 与 /teams/ui。

用法
----
    uv sync --extra snapshots
    uv run playwright install chromium
    uv run python scripts/snapshot_teams_ui.py

产物
----
    docs/images/teams-ui/*.png

所有 token / 邀请码都是脚本一次性生成的临时值，在截图前会被 JS 替换为
`team_demo_••••••` / `inv_demo_••••••` 占位串，避免任何看似真实的字符串入图。
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
from playwright.sync_api import Page, sync_playwright

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "docs" / "images" / "teams-ui"
ADMIN_TOKEN = "demo-admin-token"
VIEWPORT = {"width": 1320, "height": 900}

# 一次性临时值的替换占位
FAKE_OWNER_TOKEN = "team_demo_owner_••••••••••••"
FAKE_INVITE_CODE = "inv_demo_••••••••••••"
FAKE_MEMBER_TOKEN = "team_demo_member_••••••••••••"


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _write_yaml(path: Path, content: str) -> Path:
    path.write_text(content.strip() + "\n", encoding="utf-8")
    return path


def _app_config(db_path: Path) -> str:
    return f"""
app:
  workspace_id: default
  public_base_url: http://localhost:5230
  timezone: Asia/Shanghai
database:
  path: {db_path}
taxonomy:
  path: {db_path.parent / "taxonomy.yaml"}
prompts:
  path: {db_path.parent / "prompts.yaml"}
security:
  admin_token_env: SIDECAR_ADMIN_TOKEN
memos:
  base_url_env: MEMOS_BASE_URL
  api_token_env: MEMOS_API_TOKEN
  webhook_url_env: MEMOS_WEBHOOK_URL
  request_timeout_seconds: 5
  ingestion_mode: webhook
  poll_page_size: 20
  admin_entry_enabled: false
  admin_entry_title: Memosima 管理入口
  admin_entry_visibility: PRIVATE
worker:
  poll_interval_seconds: 0.01
  max_attempts: 2
  create_probe_comment: false
limits:
  max_attachment_mb: 1
  allowed_parse_extensions:
    - .txt
    - .md
"""


def _models_config() -> str:
    return """
default_provider: openrouter
providers:
  openrouter:
    base_url: https://openrouter.ai/api/v1
    api_key_env: OPENROUTER_API_KEY
    default_model: google/gemma-3-27b-it
    temperature: 0.1
    max_tokens:
    response_format: json_object
    extra_body: {}
"""


def _wait_health(base: str, timeout: float = 20.0) -> None:
    start = time.time()
    last = ""
    while time.time() - start < timeout:
        try:
            r = httpx.get(f"{base}/health", timeout=2.0)
            if r.status_code == 200:
                return
            last = f"status={r.status_code}"
        except Exception as e:
            last = str(e)
        time.sleep(0.3)
    raise RuntimeError(f"sidecar did not become healthy in {timeout}s; last={last}")


def _seed_demo_data(base: str) -> dict:
    """造一个 Platform 团队，含 owner（管理员合成）+ 1 名 editor + 4 条词条 + 2 张邀请。"""
    admin = {"Authorization": f"Bearer {ADMIN_TOKEN}"}

    r = httpx.post(f"{base}/admin/teams", headers=admin, json={
        "slug": "platform",
        "name": "Platform 团队",
        "description": "基础架构 / SRE / 运维知识沉淀",
        "owner_display_name": "张三 (Owner)",
    })
    r.raise_for_status()
    team_payload = r.json()
    owner_token = team_payload["owner_token"]

    owner = {"Authorization": f"Bearer {owner_token}"}

    # 邀请 1：editor，限 5 次
    r = httpx.post(f"{base}/teams/platform/invites", headers=owner, json={
        "role": "editor", "max_uses": 5,
    })
    r.raise_for_status()
    invite_payload = r.json()
    invite_code = invite_payload["code"]

    # 邀请 2：viewer，无限次（用于让邀请列表看起来更真实）
    httpx.post(f"{base}/teams/platform/invites", headers=owner, json={
        "role": "viewer", "max_uses": 0,
    }).raise_for_status()

    # 邀请 3：editor 1 次，随后撤销，演示「已撤销」状态
    r = httpx.post(f"{base}/teams/platform/invites", headers=owner, json={
        "role": "editor", "max_uses": 1,
    })
    r.raise_for_status()
    revoked_id = r.json()["id"]
    httpx.delete(
        f"{base}/teams/platform/invites/{revoked_id}", headers=owner
    ).raise_for_status()

    # 编辑者用第一张邀请加入
    r = httpx.post(f"{base}/teams/join", json={
        "code": invite_code,
        "display_name": "李四 (Editor)",
    })
    r.raise_for_status()
    member_payload = r.json()
    member_token = member_payload["token"]

    editor = {"Authorization": f"Bearer {member_token}"}

    entries = [
        {
            "title": "PostgreSQL 16 升级 Checklist",
            "body": (
                "1. 备份主库与所有备库\n"
                "2. 双写期间验证 wal_level=logical\n"
                "3. 切流后立刻 REINDEX 所有 hash 索引（PG16 不再支持 hash 索引 WAL 重放）\n"
                "4. 24h 内观察 pg_stat_replication 与慢查询日志"
            ),
            "tags": ["#postgres", "#runbook", "#db", "#upgrade"],
        },
        {
            "title": "K8s 节点 NotReady 排查 SOP",
            "body": (
                "现象：kubectl get nodes 显示 NotReady。\n"
                "1. systemctl status kubelet\n"
                "2. journalctl -u kubelet -n 200\n"
                "3. 检查 /var/lib/kubelet 磁盘是否打满\n"
                "4. 必要时 drain → reboot → uncordon"
            ),
            "tags": ["#k8s", "#runbook", "#sop"],
        },
        {
            "title": "Caddy 反代 WebSocket 配置范例",
            "body": (
                "reverse_proxy /ws/* upstream:8080 {\n"
                "  header_up Connection {http.request.header.Connection}\n"
                "  header_up Upgrade {http.request.header.Upgrade}\n"
                "}\n"
                "注意：必须保留原始 Host 头，否则下游会 400。"
            ),
            "tags": ["#caddy", "#websocket", "#gateway"],
        },
        {
            "title": "团队周会模板",
            "body": (
                "- 上周完成事项（每人 ≤ 3 条）\n"
                "- 本周计划与依赖阻塞\n"
                "- Lessons learned / 复盘\n"
                "- 风险登记簿 review"
            ),
            "tags": ["#meeting", "#template"],
        },
    ]
    for entry in entries:
        httpx.post(
            f"{base}/teams/platform/entries", headers=editor, json=entry
        ).raise_for_status()

    return {
        "admin_token": ADMIN_TOKEN,
        "owner_token": owner_token,
        "member_token": member_token,
        "invite_code": invite_code,
    }


# ---------- Playwright 辅助 ----------

MASK_SCRIPT = (
    "(function(opts){"
    # 1) 显式以 team_ / inv_ 开头的字符串占位
    "  document.querySelectorAll('.secret-box, code').forEach(function(el){"
    "    var t = (el.textContent || '').trim();"
    "    if (t.indexOf('team_') === 0) el.textContent = opts.owner;"
    "    else if (t.indexOf('inv_') === 0) el.textContent = opts.invite;"
    "  });"
    # 2) 团队 UI 邀请表内每行第一格的 <code> 都是邀请码本体（后端不带 inv_ 前缀，
    #    所以这里按位置一并替换为占位）
    "  document.querySelectorAll('#inviteListBody tr code').forEach(function(el){"
    "    el.textContent = opts.invite;"
    "  });"
    # 3) admin /teams/{slug}/invites 列表里的 code 列同理（结构相同）
    "  document.querySelectorAll('[data-panel=\"team-invites\"] table code').forEach(function(el){"
    "    el.textContent = opts.invite;"
    "  });"
    "})"
)


def _mask_secrets(page: Page) -> None:
    page.evaluate(
        MASK_SCRIPT + "({owner: %r, invite: %r})" % (FAKE_OWNER_TOKEN, FAKE_INVITE_CODE)
    )


def _save(page: Page, name: str) -> None:
    # 截图前统一抹掉一次性 token / 邀请码
    _mask_secrets(page)
    out = OUT / name
    page.screenshot(path=str(out), full_page=False)
    print(f"  → {out.relative_to(REPO)}")


# ---------- admin UI ----------

def _admin_goto_panel(page: Page, panel: str) -> None:
    """通过设置 hash 触发 activatePanel，再等到对应 section 真的 visible 再返回。"""
    page.evaluate(f"() => {{ window.location.hash = '{panel}'; }}")
    page.wait_for_selector(
        f"section[data-panel='{panel}'].active", state="visible", timeout=5000
    )
    page.wait_for_timeout(400)


def shoot_admin_ui(page: Page, base: str) -> None:
    print("[admin] 注入 admin token 并加载 /admin/ui")
    page.goto(f"{base}/admin/ui", wait_until="domcontentloaded")
    page.evaluate(
        "(t) => localStorage.setItem('memosima.adminToken', t)", ADMIN_TOKEN
    )
    page.reload(wait_until="domcontentloaded")
    page.wait_for_timeout(800)

    # 非团队 panel：直接 hash 切换 + 截图，覆盖运维/开发/配置 3 类手册需要的画面
    GENERIC_PANELS = [
        ("overview", "admin-overview.png"),
        ("jobs", "admin-jobs.png"),
        ("tags", "admin-tags.png"),
        ("prompts", "admin-prompts.png"),
        ("models", "admin-models.png"),
        ("reminders", "admin-reminders.png"),
        ("vector-search", "admin-vector-search.png"),
        ("backup", "admin-backup.png"),
        ("memos", "admin-memos.png"),
        ("docparser", "admin-docparser.png"),
        ("qa", "admin-qa.png"),
        ("reprocess", "admin-reprocess.png"),
        ("logs", "admin-logs.png"),
    ]
    for panel, fname in GENERIC_PANELS:
        try:
            _admin_goto_panel(page, panel)
            # 列表/详情类 panel 通常 600ms 内由后端拉完
            page.wait_for_timeout(600)
            _save(page, fname)
        except Exception as exc:
            print(f"  ! skip {panel}: {exc}")

    # 团队列表
    _admin_goto_panel(page, "team-list")
    page.wait_for_timeout(400)
    _save(page, "admin-team-list.png")

    # 触发 owner_token reveal dialog（先填表 → 提交） — 不真创建，仅截图
    # 这里换个思路：用 JS 直接打开 ownerTokenDialog 并塞入假值，避免造一个新团队
    page.evaluate(
        f"""
        () => {{
          const dlg = document.getElementById('ownerTokenDialog');
          const team = document.getElementById('ownerTokenTeam');
          const val = document.getElementById('ownerTokenValue');
          if (team) team.value = 'platform · Platform 团队';
          if (val) val.value = {FAKE_OWNER_TOKEN!r};
          if (dlg && typeof dlg.showModal === 'function') dlg.showModal();
        }}
        """
    )
    page.wait_for_timeout(400)
    _save(page, "admin-owner-token-dialog.png")
    page.evaluate("() => { const d = document.getElementById('ownerTokenDialog'); if (d) d.close(); }")
    page.wait_for_timeout(300)

    # 成员
    _admin_goto_panel(page, "team-members")
    sel = page.locator("#memberTeamSelect")
    if sel.count():
        sel.select_option("platform")
        page.wait_for_timeout(800)
    _save(page, "admin-team-members.png")

    # 邀请
    _admin_goto_panel(page, "team-invites")
    sel = page.locator("#inviteTeamSelect")
    if sel.count():
        sel.select_option("platform")
        page.wait_for_timeout(800)
    _save(page, "admin-team-invites.png")

    # 词条
    _admin_goto_panel(page, "team-entries")
    sel = page.locator("#entryTeamSelect")
    if sel.count():
        sel.select_option("platform")
        page.wait_for_timeout(800)
    _save(page, "admin-team-entries.png")


# ---------- teams UI（成员视角）----------

def shoot_teams_ui_onboard(page: Page, base: str) -> None:
    print("[teams] /teams/ui onboarding（无团队状态）")
    page.context.clear_cookies()
    page.goto(f"{base}/teams/ui", wait_until="domcontentloaded")
    page.evaluate("() => { localStorage.clear(); }")
    page.reload(wait_until="domcontentloaded")
    page.wait_for_timeout(400)
    _save(page, "teams-onboard.png")


def shoot_teams_ui_member(page: Page, base: str, member_token: str) -> None:
    print("[teams] /teams/ui editor 视角（词条 / 检索 / 编辑 dialog）")
    page.goto(f"{base}/teams/ui", wait_until="domcontentloaded")
    page.evaluate(
        """
        (token) => {
          const map = {
            "platform": {
              token: token,
              displayName: "李四 (Editor)",
              teamName: "Platform 团队",
              role: "editor",
              joinedAt: new Date().toISOString(),
            }
          };
          localStorage.setItem("memosima.teams.tokens", JSON.stringify(map));
          localStorage.setItem("memosima.teams.active", "platform");
        }
        """,
        member_token,
    )
    page.reload(wait_until="domcontentloaded")
    page.wait_for_timeout(1500)
    _save(page, "teams-entries.png")

    # 打开编辑 dialog
    edit_btn = page.locator("[data-action='edit-entry']").first
    if edit_btn.count():
        edit_btn.click()
        page.wait_for_timeout(700)
        _save(page, "teams-edit-dialog.png")
        page.evaluate(
            "() => { const d = document.getElementById('entryEditDialog'); if (d) d.close(); }"
        )
        page.wait_for_timeout(200)

    # 切到检索 tab，填关键字 + 执行检索
    _teams_switch_tab(page, "search")
    page.locator("#searchQuery").fill("PostgreSQL")
    # 关掉向量（本机大概率没配 SILICONFLOW_API_KEY，避免界面卡在 loading）
    use_vec = page.locator("#searchUseVector")
    if use_vec.is_checked():
        use_vec.uncheck()
    page.locator("#searchRunBtn").click()
    page.wait_for_timeout(1200)
    page.locator("#promptRunBtn").click()
    page.wait_for_timeout(1500)
    _save(page, "teams-search-qa.png")


def _teams_switch_tab(page: Page, tab: str) -> None:
    """teams_ui 的 switchTab 是 IIFE 内的闭包，无法直接 evaluate 调用，
    所以用「先 setAttribute / toggle hidden，再触发一次 click 让数据 loader 跑」的方式。"""
    page.evaluate(
        f"""
        (tab) => {{
          document.querySelectorAll('.tab-btn').forEach(btn => {{
            btn.setAttribute('aria-selected', String(btn.dataset.tab === tab));
          }});
          document.querySelectorAll('[data-tab-panel]').forEach(panel => {{
            panel.classList.toggle('hidden', panel.dataset.tabPanel !== tab);
          }});
          const btn = document.querySelector(`.tab-btn[data-tab='${{tab}}']`);
          if (btn) btn.click();
        }}
        """,
        tab,
    )
    page.wait_for_timeout(900)


def shoot_teams_ui_owner(page: Page, base: str, owner_token: str) -> None:
    print("[teams] /teams/ui owner 视角（成员 / 邀请 / reveal dialog）")
    page.goto(f"{base}/teams/ui", wait_until="domcontentloaded")
    page.evaluate(
        """
        (token) => {
          const map = {
            "platform": {
              token: token,
              displayName: "张三 (Owner)",
              teamName: "Platform 团队",
              role: "owner",
              joinedAt: new Date().toISOString(),
            }
          };
          localStorage.setItem("memosima.teams.tokens", JSON.stringify(map));
          localStorage.setItem("memosima.teams.active", "platform");
        }
        """,
        owner_token,
    )
    page.reload(wait_until="domcontentloaded")
    page.wait_for_timeout(1200)

    _teams_switch_tab(page, "members")
    _save(page, "teams-members.png")

    _teams_switch_tab(page, "invites")
    _save(page, "teams-invites.png")

    # invite reveal dialog（直接塞假值打开，避免新增一条真邀请）
    page.evaluate(
        f"""
        () => {{
          const dlg = document.getElementById('inviteRevealDialog');
          const box = document.getElementById('inviteRevealCode');
          const meta = document.getElementById('inviteRevealMeta');
          if (box) box.textContent = {FAKE_INVITE_CODE!r};
          if (meta) meta.textContent = '角色：editor · 上限：5 次 · 过期时间：—';
          if (dlg && typeof dlg.showModal === 'function') dlg.showModal();
        }}
        """
    )
    page.wait_for_timeout(400)
    _save(page, "teams-invite-reveal.png")


# ---------- 主流程 ----------

def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        app_yaml = _write_yaml(td_path / "app.yaml", _app_config(td_path / "sidecar.db"))
        models_yaml = _write_yaml(td_path / "models.yaml", _models_config())
        port = _pick_free_port()
        base = f"http://127.0.0.1:{port}"

        env = os.environ.copy()
        env.update({
            "SIDECAR_ADMIN_TOKEN": ADMIN_TOKEN,
            "MEMOS_BASE_URL": "http://localhost:5230",
            "MEMOS_API_TOKEN": "snapshot-placeholder",
            "MEMOSIMA_APP_CONFIG": str(app_yaml),
            "MEMOSIMA_MODELS_CONFIG": str(models_yaml),
        })
        # 避免任何外部嵌入 / 推理 / 解析服务被误调用，并且让 /admin/models、
        # /admin/vector-search、/admin/docparser、/admin/reminders、
        # /admin/memos 等面板渲染为「未配置」干净状态，不会把宿主机的真实
        # API Key / token 泄漏进截图。
        for _leaky in (
            "SILICONFLOW_API_KEY",
            "DEEPSEEK_API_KEY",
            "OPENROUTER_API_KEY",
            "OPENAI_API_KEY",
            "MINERU_API_TOKEN",
            "REMINDER_WEBHOOK_URL",
            "MEMOS_WEBHOOK_URL",
        ):
            env.pop(_leaky, None)

        cmd = [
            sys.executable, "-m", "uvicorn",
            "memosima.api.app:create_app",
            "--factory",
            "--host", "127.0.0.1",
            "--port", str(port),
            "--log-level", "warning",
        ]
        # create_app 接受位置参数 (app_config, models_config)；uvicorn factory 不能传参，
        # 但 create_app() 默认会读环境变量 MEMOSIMA_APP_CONFIG / MEMOSIMA_MODELS_CONFIG 不一定生效。
        # 改为通过一个临时 wrapper 模块走 factory。
        wrapper = td_path / "snapshot_app_factory.py"
        wrapper.write_text(
            "from memosima.api.app import create_app\n"
            f"def factory():\n"
            f"    return create_app({str(app_yaml)!r}, {str(models_yaml)!r})\n",
            encoding="utf-8",
        )
        env["PYTHONPATH"] = f"{td_path}{os.pathsep}{env.get('PYTHONPATH', '')}"
        cmd = [
            sys.executable, "-m", "uvicorn",
            "snapshot_app_factory:factory",
            "--factory",
            "--host", "127.0.0.1",
            "--port", str(port),
            "--log-level", "warning",
        ]

        print(f"[boot] 启动 sidecar on {base}")
        proc = subprocess.Popen(cmd, env=env, cwd=str(td_path))
        try:
            _wait_health(base)
            print("[boot] sidecar 已就绪，开始造 demo 数据")
            seeded = _seed_demo_data(base)
            print("[boot] demo 数据完成")

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(viewport=VIEWPORT, device_scale_factor=2)
                page = context.new_page()

                shoot_admin_ui(page, base)
                shoot_teams_ui_onboard(page, base)
                shoot_teams_ui_member(page, base, seeded["member_token"])
                shoot_teams_ui_owner(page, base, seeded["owner_token"])

                browser.close()
            print(f"\n[done] 所有截图已保存到 {OUT.relative_to(REPO)}/")
            return 0
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
