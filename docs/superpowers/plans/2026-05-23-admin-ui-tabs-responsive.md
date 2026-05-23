# 管理配置页标签页与响应式改造实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 将 `/admin/ui` 从长页混排改为工作区式标签页，并补齐响应式布局、锚点兼容和相关文档。

**架构：** 继续保留单文件 HTML 管理页，后端 API 不变。通过 HTML 分区、CSS 响应式规则和少量原生 JavaScript 实现标签页切换、hash 映射、详情侧栏和窄屏降级。

**技术栈：** FastAPI `TestClient`、内嵌 HTML/CSS/JavaScript、Nx target（`npx nx test sidecar`、`npx nx run sidecar:compile`）。

---

## 文件结构

- 修改：`tests/test_api.py`。扩展 `/admin/ui` HTML 结构断言，先证明当前页面缺少标签页结构。
- 修改：`src/memosima/api/admin_ui.py`。重排 HTML、CSS 和 JavaScript，实现标签页、响应式布局、hash 映射和现有功能绑定。
- 修改：`docs/使用手册.html`。同步说明管理页面的标签页和新增锚点。
- 修改：`docs/配置说明.html`。同步 `/admin/ui` 锚点列表。

## 任务 1：为标签页结构补红灯测试

**文件：**

- 修改：`tests/test_api.py`

- [ ] **步骤 1：编写失败的测试**

在 `test_admin_ui_returns_debug_page_without_exposing_token` 中新增 HTML 结构断言：

```python
    assert 'class="shell"' in response.text
    assert 'role="tablist"' in response.text
    assert 'data-tab-target="overview"' in response.text
    assert 'data-tab-target="jobs"' in response.text
    assert 'data-tab-target="tags"' in response.text
    assert 'data-tab-target="prompts"' in response.text
    assert 'data-tab-target="models"' in response.text
    assert 'data-tab-target="reminders"' in response.text
    assert 'data-tab-target="backup"' in response.text
    assert 'data-panel="overview"' in response.text
    assert 'data-panel="tags"' in response.text
    assert 'data-panel="backup"' in response.text
    assert "showPanelFromHash" in response.text
    assert "hashPanelMap" in response.text
```

- [ ] **步骤 2：运行测试验证失败**

运行：

```bash
npx nx test sidecar -- tests/test_api.py::test_admin_ui_returns_debug_page_without_exposing_token -q
```

预期：测试失败，失败原因是缺少 `class="shell"` 或 `role="tablist"`。

- [ ] **步骤 3：提交红灯测试**

```bash
git add tests/test_api.py
git commit -m "测试：补充管理页标签页结构断言" \
  -m "为 /admin/ui 增加标签导航、面板和 hash 映射相关断言。" \
  -m "先形成红灯测试，约束后续管理页重排不泄漏 token。"
```

## 任务 2：实现标签页和响应式结构

**文件：**

- 修改：`src/memosima/api/admin_ui.py`
- 测试：`tests/test_api.py`

- [ ] **步骤 1：重排 HTML**

将现有 `<main>` 内的两栏长页改成：

```html
<main class="shell">
  <header class="topbar">...</header>
  <nav class="tabs" role="tablist" aria-label="管理功能">
    <button class="tab active" type="button" role="tab" data-tab-target="overview">概览</button>
    ...
  </nav>
  <section class="tab-panel active" data-panel="overview">...</section>
  <section class="tab-panel" data-panel="jobs">...</section>
  <section class="tab-panel" data-panel="tags">...</section>
  <section class="tab-panel" data-panel="prompts">...</section>
  <section class="tab-panel" data-panel="models">...</section>
  <section class="tab-panel" data-panel="reminders">...</section>
  <section class="tab-panel" data-panel="backup">...</section>
</main>
```

保留所有现有元素 ID，例如 `tokenInput`、`healthOutput`、`jobsBody`、`candidatesBody`、`tagSummaryOutput`、`modelProviderSelect`、`promptSystem`、`remindersBody`、`restoreBackupInput`。

- [ ] **步骤 2：更新 CSS**

新增或替换这些核心类：

```css
.shell { max-width: 1440px; margin: 0 auto; padding: 20px; }
.topbar { display: grid; grid-template-columns: minmax(220px, 1fr) minmax(360px, 620px); gap: 16px; align-items: start; }
.tabs { display: flex; gap: 6px; overflow-x: auto; margin: 16px 0; padding-bottom: 2px; }
.tab { min-height: 36px; border-radius: 8px; }
.tab.active { background: var(--accent); border-color: var(--accent); color: #fff; }
.tab-panel { display: none; }
.tab-panel.active { display: block; }
.workspace { display: grid; grid-template-columns: minmax(0, 1fr) 360px; gap: 16px; align-items: start; }
.overview-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; }
.table-wrap { max-width: 100%; overflow-x: auto; }
@media (max-width: 1099px) {
  .topbar, .workspace, .overview-grid { grid-template-columns: 1fr; }
}
@media (max-width: 700px) {
  .shell { padding: 12px; }
  .toolbar, .actions { align-items: stretch; }
  button { min-height: 36px; }
}
```

- [ ] **步骤 3：更新 JavaScript 标签页逻辑**

添加：

```javascript
const hashPanelMap = {
  overview: { panel: "overview" },
  jobs: { panel: "jobs" },
  "tag-candidates": { panel: "tags", focus: "tag-candidates" },
  "tag-summary": { panel: "tags", focus: "tag-summary" },
  prompts: { panel: "prompts" },
  models: { panel: "models" },
  reminders: { panel: "reminders" },
  backup: { panel: "backup" }
};

function activatePanel(panelName, options = {}) {
  ...
}

function showPanelFromHash() {
  ...
}
```

要求：

- 点击 `data-tab-target` 按钮时更新 `window.location.hash`。
- `hashchange` 调用 `showPanelFromHash()`。
- 页面初始化时调用 `showPanelFromHash()`。
- `#tag-candidates` 和 `#tag-summary` 激活「标签」面板后滚动到对应区域。

- [ ] **步骤 4：运行单测验证通过**

运行：

```bash
npx nx test sidecar -- tests/test_api.py::test_admin_ui_returns_debug_page_without_exposing_token -q
```

预期：测试通过。

- [ ] **步骤 5：提交页面实现**

```bash
git add src/memosima/api/admin_ui.py tests/test_api.py
git commit -m "功能：重构管理页为标签页布局" \
  -m "将管理配置页改为概览、任务、标签、AI 配置、模型、提醒和备份标签页。" \
  -m "新增响应式布局、hash 映射和详情面板，保留现有管理接口与 token 策略。"
```

## 任务 3：同步使用文档

**文件：**

- 修改：`docs/使用手册.html`
- 修改：`docs/配置说明.html`

- [ ] **步骤 1：更新文档内容**

在 `docs/使用手册.html` 的「打开调试管理页面」段落中说明：

- 页面按「概览、任务、标签、AI 配置、模型、提醒、备份」聚合功能。
- 支持 `#jobs`、`#tag-candidates`、`#tag-summary`、`#models`、`#backup`、`#prompts`、`#reminders` 锚点直达。
- 窄屏下表格在容器内横向滚动，详情区域移动到列表下方。

在 `docs/配置说明.html` 的管理页面锚点段落中补充：

- `#prompts`。
- `#reminders`。
- `#overview`。

- [ ] **步骤 2：检查文档差异**

运行：

```bash
git diff -- docs/使用手册.html docs/配置说明.html
```

预期：只包含管理页面说明更新，不出现真实 token、API key 或本地私密地址。

- [ ] **步骤 3：提交文档**

```bash
git add docs/使用手册.html docs/配置说明.html
git commit -m "文档：更新管理页标签页使用说明" \
  -m "同步管理配置页的功能标签、响应式行为和新增锚点。" \
  -m "仅更新使用说明与配置说明，不包含机密信息。"
```

## 任务 4：完整验证

**文件：**

- 读取：`src/memosima/api/admin_ui.py`
- 读取：`docs/使用手册.html`
- 读取：`docs/配置说明.html`

- [ ] **步骤 1：运行完整测试**

```bash
npx nx test sidecar
```

预期：全部 pytest 通过。

- [ ] **步骤 2：运行编译检查**

```bash
npx nx run sidecar:compile
```

预期：Python 源码和测试编译通过。

- [ ] **步骤 3：人工核对规格验收项**

核对：

- `/admin/ui` 默认具备「概览」标签。
- 页面 HTML 包含 `#jobs`、`#tag-candidates`、`#tag-summary`、`#models`、`#backup`、`#prompts`、`#reminders` 对应映射。
- 任务、候选标签、标签总结和提醒共用详情输出，不丢失现有操作按钮绑定。
- 文档已同步。

- [ ] **步骤 4：提交最终验证记录（如有测试或文档调整）**

如果任务 4 产生代码或文档调整，按功能点提交；如果没有新改动，不创建空提交。
