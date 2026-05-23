# Memosima

Memosima 是基于 Memos 的个人 AI 知识库 Sidecar 服务。Memos 负责采集和保存原始知识，Sidecar 负责 AI 整理、标签治理、澄清评论、附件解析和后续检索能力。

---

## 当前状态

已完成 P0、P1、P2 核心闭环，并开始 P3 文本附件解析基础。

- **Caddy 网关统一入口**：默认从 `http://localhost:8080/` 访问 Memos，从 `/admin/*`、`/health`、`/webhooks/*` 访问 Sidecar。
- **Webhook 与任务系统**：Memos webhook 接入和 SQLite 任务系统。
- **AI 智能整理**：创建 memo 时进行整理，支持 DeepSeek、、OpenRouter 等 OpenAI-compatible LLM 和本地模板回退。
- **Memos 原生关联**：使用 Memos 原生 `REFERENCE` relation 关联原始 memo 与 AI memo。
- **管理与调试页面**：内置 `/admin/ui` 页面，用于查看任务、重试任务、审核候选标签、备份和恢复 Sidecar 数据。
- **系统入口自动维护**：worker 可在 Memos 中自动维护 `#系统/Memosima` 管理入口 memo，AI 整理 memo 也会附带管理页面和候选标签审核链接。
- **标签治理**：支持候选标签审核和审核后 active 生效。
- **无标签自动推荐**：当用户原始 memo 没有业务标签时，LLM 可从正文自动建议正式标签和候选标签；新标签仍需人工审核。
- **提示词热加载与覆盖**：LLM 提示词从 `config/prompts.yaml` 加载，管理页面可保存默认提示词，也可在重试时临时覆盖。
- **澄清评论机制**：待澄清评论和 `waiting_user` 状态。
- **附件Markdown解析**：`.txt`、`.md` 附件解析为 artifact；Word、Excel、PPT、PDF 附件可通过 MinerU 在线服务转成 Markdown 后进入同一 AI 整理流程。
- **智能提醒系统**：`#提醒` 时间识别和一次性定时通知，支持 Bark 兼容 webhook。
- **备份与恢复**：管理页面支持下载 Sidecar 备份包，并从备份包恢复 Sidecar SQLite 数据库。

> [!NOTE]
> **未完成范围**：drawio/Mind Elixir 专用解析、向量索引、问答、自动文档、Memos 主库备份恢复。

---

## 智能索引与语义检索 (CodeGraph & Semble)

本项目已集成两款现代 AI 协同检索工具，方便 AI 助手在开发和运行时进行高效的代码发现与语义检索。

### 1. CodeGraph (智能代码知识图谱)
CodeGraph 在本地构建 SQLite-backed 符号关系与调用图谱，支持增量同步，极大地提升了 AI 智能体的代码分析效率。

* **查看索引状态**：
  ```bash
  npx codegraph status
  ```
* **增量同步索引**：
  ```bash
  npx codegraph sync
  ```

### 2. Semble (语义与词法代码检索)
Semble 结合了静态 Model2Vec 向量模型（`potion-code-16M`）与 BM25 词法算法，运行于 CPU，能够在不消耗额外 Token 的情况下精确定位代码片段。

* **自然语言语义检索**：
  ```bash
  uv run semble search "memosima api" .
  ```
* **查找相似代码实现**：
  ```bash
  uv run semble find-related src/memosima/api/app.py 360 .
  ```

> [!IMPORTANT]
> **无冲突隔离**：项目已在 `.gitignore` 中配置排除 `.local/`、`.antigravitycli/` 和 `.codex/` 目录。在未来的增量索引中，任何工具都会自动跳过 AI 智能体运行时产生的内部缓存文件和原始数据，确保只索引代码、配置文件与文档。

---

## 快速开始

```bash
cp .env.example .env
npx nx run sidecar:up
curl http://localhost:8080/health
```

默认 Docker Compose 会启动 `gateway`、`memos`、`sidecar` 和 `sidecar-worker`。Caddy 网关只暴露一个宿主机入口：`http://localhost:8080/` 进入 Memos，`http://localhost:8080/admin/ui` 进入 Sidecar 管理页面，`http://localhost:8080/health` 返回 Sidecar 健康状态。Memos 的 `5230` 和 Sidecar 容器内部 `8080` 默认不直接暴露到宿主机；需要改宿主机端口时可设置 `GATEWAY_PORT`。

调试管理页面不会读取服务器端密钥，需要手动输入 `SIDECAR_ADMIN_TOKEN`，并只保存在当前浏览器的 `localStorage`。页面也可以编辑默认 LLM 提示词，或在重试任务时只临时覆盖当前任务使用的提示词。默认开启 Memos 内管理入口，worker 空闲时会自动创建或更新一条 `#系统/Memosima` memo，入口链接由 `app.public_base_url` 生成。

---

## 常用开发命令

所有依赖安装、测试、构建等命令均应优先通过 Nx target 执行：

```bash
# 运行单元测试
npx nx test sidecar

# 编译代码验证
npx nx run sidecar:compile

# 构建 Docker 镜像
npx nx build sidecar

# 探测 Memos 服务状态
npx nx run sidecar:probe-memos
```

---

## 提醒用法

在 memo 中写入 `#提醒` 和明确时间，例如 `#提醒 明天 09:30 提交周报`。worker 会在整理该 memo 时调用默认模型抽取时间，创建持久化提醒；到期后通过 `REMINDER_WEBHOOK_URL` 发送 `title`/`body` 表单通知。时间模糊或置信度不足时，Sidecar 会在原 memo 下评论要求补充，不会阻塞普通 AI 整理。

---

## 备份恢复

管理页面的“备份恢复”区域可以下载 Sidecar 备份 ZIP。备份包含 Sidecar SQLite 快照和非机密配置文件；恢复时只替换 Sidecar SQLite，不会自动覆盖配置文件，也不会备份或恢复 Memos 主库。

---

## 相关文档

- [普通用户使用手册](docs/普通用户使用手册.html)
- [使用手册](docs/使用手册.html)
- [配置说明](docs/配置说明.html)
- [开发运行说明](docs/开发运行说明.html)
- [API 探针记录](docs/API探针记录.html)
- [开发计划与验收标准](开发计划与验收标准-个人AI知识库系统.html)
- [技术架构设计](技术架构设计-个人AI知识库系统.html)
- [PRD](PRD-个人AI知识库系统.html)
