# 个人 AI 知识库系统技术架构设计

## 1. 架构原则

1. 不魔改 Memos，使用 API、Webhook 和资源接口完成旁路增强。
2. 原始资料与 AI 生成资料分离，避免 AI 覆盖用户原文。
3. 标签树在 Sidecar 中强管控，Memos 中只承载最终标签文本。
4. 后台任务异步化，Webhook 接收与 AI 处理解耦。
5. 默认轻量本地部署，优先 SQLite，预留替换能力。
6. 所有代码完成标准为真实集成测试通过。

## 2. 总体架构

```text
┌──────────────────────────┐
│          Memos            │
│  UI / API / Webhook       │
│  SQLite / Attachments     │
└─────────────┬────────────┘
              │ Webhook + API
              ▼
┌──────────────────────────┐
│     AI Sidecar Service    │
│ FastAPI + Background Jobs │
└─────────────┬────────────┘
              │
┌─────────────┼─────────────────────────────────────┐
│             │                                     │
▼             ▼                                     ▼
Memos      LLM Gateway                         Local Storage
Client     LiteLLM/OpenAI-compatible           SQLite + sqlite-vec
│          OpenRouter/Qwen/DeepSeek/Custom      Config + Backups
│
▼
Attachment Parsers
txt/md/docx/xlsx/pdf/drawio/mind-elixir-json
```

## 3. 部署架构

第一版采用 Docker Compose，部署在 NAS 或 Linux。

```text
memosima/
  docker-compose.yml
  .env
  config/
    app.yaml
    taxonomy.yaml
    doc-generation.yaml
    models.yaml
  data/
    memos/
    sidecar/
    backups/
  logs/
```

推荐服务：

| 服务 | 说明 |
| --- | --- |
| `memos` | Memos 主服务 |
| `sidecar-api` | FastAPI 接收 webhook、管理接口 |
| `sidecar-worker` | 后台任务、附件解析、AI 调用、索引、文档生成 |
| `backup` | 可选定时备份任务，可与 worker 合并 |

MVP 可将 `sidecar-api` 与 `sidecar-worker` 放在同一进程中，后续再拆分。

## 4. 模块设计

### 4.1 API 模块

职责：

- 接收 Memos webhook。
- 提供标签审核管理接口。
- 提供手动文档生成接口。
- 提供备份与恢复检查接口。
- 提供健康检查。

建议接口：

```text
POST /webhooks/memos
GET  /health
GET  /admin/tag-candidates
POST /admin/tag-candidates/{id}/approve
POST /admin/tag-candidates/{id}/reject
POST /admin/documents/generate
POST /admin/backups
GET  /admin/backups
POST /admin/backups/{id}/verify
```

### 4.2 Memos Client

职责：

- 拉取 memo 列表和详情。
- 创建 AI 整理 memo。
- 创建 AI 文档 memo。
- 创建评论用于澄清。
- 建立 memo 关联或在正文中写入来源链接。
- 下载附件资源。

需要用集成测试校验 Memos 当前版本接口，避免依赖过期路径。

### 4.3 任务系统

Webhook 不直接执行 AI 处理，只创建任务。

任务类型：

```text
process_memo
parse_attachment
review_tag_candidate
generate_document
index_memo
answer_question
backup_create
backup_verify
backup_restore
```

MVP 可用 SQLite 任务表加轮询 worker。后续可替换为 Redis Queue、Celery 或 Dramatiq。

### 4.4 LLM 网关

使用 OpenAI-compatible 抽象，支持：

- OpenRouter。
- Qwen。
- DeepSeek。
- 自定义 base_url、api_key、model。

配置示例：

```yaml
providers:
  openrouter:
    base_url: https://openrouter.ai/api/v1
    api_key_env: OPENROUTER_API_KEY
    default_model: openrouter/auto
  qwen:
    base_url: https://dashscope.aliyuncs.com/compatible-mode/v1
    api_key_env: DASHSCOPE_API_KEY
    default_model: qwen-plus
  deepseek:
    base_url: https://api.deepseek.com
    api_key_env: DEEPSEEK_API_KEY
    default_model: deepseek-chat
  custom:
    base_url: ${CUSTOM_LLM_BASE_URL}
    api_key_env: CUSTOM_LLM_API_KEY
    default_model: ${CUSTOM_LLM_MODEL}
```

每次 AI 调用必须记录：

- provider。
- model。
- prompt 版本。
- token 用量。
- 耗时。
- 任务 ID。
- 输出校验结果。
- 错误信息。

### 4.5 标签树模块

Sidecar 持有正式标签树、候选标签、别名和禁用词。Memos 中的标签只作为展示与检索入口。

核心能力：

- 加载标签树配置。
- 查询相似标签。
- 校验标签格式。
- 创建候选标签。
- 审核通过或拒绝。
- 导出标签树用于备份。

标签状态：

```text
active
candidate
rejected
disabled
merged
```

### 4.6 附件解析模块

解析策略：

| 格式 | 实现建议 |
| --- | --- |
| txt | 直接读取 |
| md | 保留 Markdown |
| docx | MarkItDown 或 python-docx |
| xlsx | MarkItDown 或 openpyxl |
| pdf | MarkItDown / pdfplumber 提取文本层，暂不 OCR |
| drawio | 解析 XML，提取图名、节点文本、连接关系 |
| Mind Elixir JSON | 解析节点树，转 Markdown 大纲 |

安全限制：

- 文件大小上限可配置。
- MIME 与扩展名双重校验。
- 不解析未知格式。
- 解析失败保留原始附件链接和错误原因。

### 4.7 文档生成模块

文档生成配置：

```yaml
defaults:
  keep_versions: 5
  output_tag: "#系统/AI文档"
rules:
  - name: project_daily_summary
    scope: "#项目"
    depth: 2
    trigger:
      type: schedule
      cron: "0 2 * * *"
    template: project_summary
  - name: approved_tag_document
    trigger:
      type: tag_approved
    template: tag_document
```

生成流程：

```text
确定范围
-> 查询 memo 与 AI 整理结果
-> 排除旧版 AI 文档或按策略引用
-> 组织上下文
-> 调用 LLM 生成文档
-> 新建 AI 文档 memo
-> 建立来源关联
-> 清理超过 N 个版本的旧文档
-> 写入索引
```

### 4.8 RAG 与问答模块

用户体验上不暴露传统 chunk。内部使用语义单元。

语义单元类型：

- 原始 memo。
- AI 整理 memo。
- 附件段落或表格。
- AI 文档章节。
- Mind Elixir 节点路径。
- drawio 节点与连接说明。

检索策略：

1. 向量相似度检索。
2. 标签同层级和子树召回。
3. 来源 memo 关系扩展。
4. 去重与排序。
5. 生成带来源的回答。

第一版问答入口建议：

```text
用户创建 #系统/问答 memo
-> Sidecar 识别问题
-> 检索
-> 新建 AI 回答 memo
-> 关联问题 memo 与来源 memo
```

### 4.9 备份恢复模块

本地备份目录结构：

```text
backups/
  2026-05-18_210000/
    manifest.json
    memos.db
    memos-resources.tar.gz
    sidecar.db
    vector.db
    config.tar.gz
    taxonomy.yaml
    checksums.sha256
    restore.md
```

`manifest.json` 记录：

- 备份时间。
- 系统版本。
- Memos 版本。
- Sidecar 版本。
- 数据库文件列表。
- 校验和。
- 备份参数。

恢复策略：

1. 停止服务。
2. 校验备份包。
3. 备份当前数据为恢复前快照。
4. 覆盖数据文件。
5. 启动服务。
6. 执行健康检查与索引校验。

## 5. 数据库设计

### 5.1 `workspaces`

预留多人和多空间。

| 字段 | 说明 |
| --- | --- |
| `id` | 主键 |
| `name` | 工作区名称 |
| `created_at` | 创建时间 |
| `updated_at` | 更新时间 |

### 5.2 `memos`

记录 Sidecar 已处理的 memo 映射。

| 字段 | 说明 |
| --- | --- |
| `id` | 主键 |
| `workspace_id` | 工作区 |
| `memos_uid` | Memos memo UID |
| `type` | original / ai_summary / ai_document / qa |
| `source_memo_uid` | 来源 memo |
| `content_hash` | 内容哈希 |
| `status` | 状态 |
| `created_at` | 创建时间 |
| `updated_at` | 更新时间 |

### 5.3 `jobs`

| 字段 | 说明 |
| --- | --- |
| `id` | 主键 |
| `workspace_id` | 工作区 |
| `type` | 任务类型 |
| `status` | pending / running / succeeded / failed / waiting_user |
| `payload_json` | 任务输入 |
| `result_json` | 任务结果 |
| `error` | 错误 |
| `retry_count` | 重试次数 |
| `created_at` | 创建时间 |
| `updated_at` | 更新时间 |

### 5.4 `tag_nodes`

| 字段 | 说明 |
| --- | --- |
| `id` | 主键 |
| `workspace_id` | 工作区 |
| `path` | 标签路径 |
| `parent_path` | 父标签 |
| `status` | active / candidate / rejected / disabled / merged |
| `source` | human / ai |
| `reason` | AI 创建理由或人工说明 |
| `confidence` | AI 置信度 |
| `merged_to` | 合并目标 |
| `created_at` | 创建时间 |
| `updated_at` | 更新时间 |

### 5.5 `tag_aliases`

| 字段 | 说明 |
| --- | --- |
| `id` | 主键 |
| `workspace_id` | 工作区 |
| `alias` | 别名 |
| `target_path` | 正式标签 |

### 5.6 `artifacts`

| 字段 | 说明 |
| --- | --- |
| `id` | 主键 |
| `memo_uid` | 关联 memo |
| `resource_uid` | 附件资源 |
| `kind` | attachment_text / ai_summary / ai_document |
| `content_markdown` | 解析或生成内容 |
| `metadata_json` | 页码、表名、节点路径等 |
| `created_at` | 创建时间 |

### 5.7 `vector_units`

| 字段 | 说明 |
| --- | --- |
| `id` | 主键 |
| `workspace_id` | 工作区 |
| `memo_uid` | 来源 memo |
| `artifact_id` | 来源 artifact |
| `unit_type` | memo / paragraph / table / document_section / mind_node / drawio_node |
| `text` | 检索文本 |
| `tags_json` | 标签 |
| `metadata_json` | 来源信息 |
| `embedding_hash` | embedding 输入哈希 |
| `created_at` | 创建时间 |

向量本体存入 sqlite-vec 虚拟表，通过 `vector_units.id` 关联。

### 5.8 `document_versions`

| 字段 | 说明 |
| --- | --- |
| `id` | 主键 |
| `workspace_id` | 工作区 |
| `doc_key` | 文档唯一键 |
| `scope_path` | 生成范围 |
| `memo_uid` | Memos 中的文档 memo |
| `version` | 版本号 |
| `created_by_trigger` | schedule / manual / tag_approved |
| `created_at` | 创建时间 |

### 5.9 `llm_calls`

| 字段 | 说明 |
| --- | --- |
| `id` | 主键 |
| `job_id` | 任务 |
| `provider` | 供应商 |
| `model` | 模型 |
| `prompt_version` | Prompt 版本 |
| `input_tokens` | 输入 token |
| `output_tokens` | 输出 token |
| `latency_ms` | 耗时 |
| `status` | 状态 |
| `error` | 错误 |
| `created_at` | 创建时间 |

## 6. 配置设计

### 6.1 `app.yaml`

```yaml
app:
  workspace_id: default
  public_base_url: http://localhost:5230
  timezone: Asia/Shanghai
security:
  admin_token_env: SIDECAR_ADMIN_TOKEN
limits:
  max_attachment_mb: 50
  allowed_parse_extensions:
    - .txt
    - .md
    - .docx
    - .xlsx
    - .pdf
    - .drawio
    - .drawio.svg
    - .json
```

### 6.2 `taxonomy.yaml`

```yaml
system_tags:
  original: "#系统/原始记录"
  ai_summary: "#系统/AI整理"
  ai_document: "#系统/AI文档"
  pending_clarification: "#系统/待澄清"
  tag_candidate: "#系统/标签待审核"
  qa: "#系统/问答"
business_tags:
  - path: "#项目/个人AI知识库"
    status: active
aliases:
  - alias: "#AI知识库"
    target: "#项目/个人AI知识库"
disabled:
  - "#杂项"
```

### 6.3 `models.yaml`

见 LLM 网关配置。

### 6.4 `doc-generation.yaml`

见文档生成配置。

## 7. 测试策略

### 7.1 单元测试

- 标签路径校验。
- 标签相似度与别名映射。
- 附件解析器。
- Prompt 输出 schema 校验。
- 文档版本清理。
- 备份 manifest 与 checksum。

### 7.2 集成测试

- 使用真实 Memos 实例。
- 创建 memo 后触发 webhook。
- 新建 AI 整理 memo。
- 创建候选标签并审核通过。
- 解析附件并写入 artifacts。
- 生成文档并保留版本。
- 创建 `#系统/问答` memo 并生成回答。
- 执行备份和恢复校验。

### 7.3 验收测试

所有核心流程必须基于真实服务完成，不以 mock 作为完成标准。

## 8. 技术风险与处理

| 风险 | 处理 |
| --- | --- |
| Memos API 版本变化 | 固定镜像版本，启动时检查版本，集成测试覆盖 |
| Memos 标签不是强约束实体 | Sidecar 管理标签树，Memos 只展示最终标签 |
| AI 输出不稳定 | 使用结构化 JSON schema、重试、人工审核 |
| 附件解析失败 | 保留原附件，记录错误，不阻断主流程 |
| NAS 性能有限 | 后台任务限流，文档生成定时低峰执行 |
| 模型供应商差异 | OpenAI-compatible 适配层，配置化 provider |
| 备份恢复损坏 | checksum、manifest、恢复前快照 |

