# Prism (棱镜) - 个人专属 AI 知识折射库

<p align="center">
  <img src="./Prism.png" alt="Prism Logo" width="240" />
</p>

---

> 🌈 **Prism (棱镜)：光的折射与思维的绚烂**
>
> 无论是闪现的灵感、会议的摘要，还是随手拍下的网页，您丢进 Memos 的原始笔记，就像一束朴素、零散的 **白光**。
> 当这束光穿过 **Prism** 时，会被 AI 优雅地折射，化作清晰的层级大纲、精准的分级业务标签、高品质的待办事项与触手可及的 系统化知识。
> **零碎的想法进去了，出来的是一抹绚丽的知识彩虹。**

**Prism (棱镜)** 是一款专为 [Memos](https://github.com/usememos/memos) 深度定制开发的 **个人离线 AI 知识库 Sidecar 伴生系统**。
* **Memos** 负责前端超快捷地收集、记录和保存原始的想法。
* **Prism (Sidecar)** 负责在后台进行 AI 结构化整理、标签双层治理、高保真本地附件解析、智能提醒通知、离线 RAG 拼装和一键搬家管理。

---

## 💡 为什么需要 Prism？解决哪些核心痛点？

在日常使用零碎备忘（如 Memos、Flomo）记录知识时，个人用户通常会遇到以下四大痛点，而 **Prism** 正是为此量身定制的解药：

### 痛点 1：碎片化信息变成“数字坟墓”
* **现状**：随手记录了大量一两句话的笔记、会议纪要或灵感，由于缺少时间整理和规范的标题，几天后便被淹没在信息洪流中，无法重用。
* **Prism 方案 (AI 智能整理)**：Sidecar 在后台自动异步拦截新笔记，利用大语言模型（如 DeepSeek）生成**核心标题、要点摘要、下一步待办 (To-Do List)**，并自动通过原生 `REFERENCE` 关系双向锚定，将凌乱想法秒变结构化闪念卡片。

### 痛点 2：标签野蛮生长与“标签污染”
* **现状**：手动分类时，今天写了 `#部署`，明天写了 `#deployment`，后天又写了 `#deploy`，标签体系彻底混乱。或者放任 AI 乱打标签，导致标签列表瞬间膨胀上百个。
* **Prism 方案 (双层审核治理)**：独创**“正式标签 (Active)”**与**“候选标签 (Candidate)”**双层治理架构。
  - 只有经过管理员审核通过的标签才会真正应用于笔记归档。
  - AI 提出的新颖标签或用户手写的新标签，将一律扣留在“待审核 (Candidate)”队列中，并支持拼音首字母模糊归一，确保知识树结构始终优雅、干练。

### 痛点 3：非结构化文件（脑图、流程图）无法被检索
* **现状**：在笔记中上传了 Draw.io 流程图或思维导图 JSON 作为附件。普通的文本搜索工具根本无法读取其内部的文字节点，导致这部分重度知识彻底“失联”。
* **Prism 方案 (100% 本地离线高保真解析)**：
  - **Draw.io 解析**：本地使用 zlib 自动解密还原 base64 字节流并解析 XML 树，提取所有图形节点的文本，过滤多余 HTML，秒转干净 Markdown 列表。
  - **Mind Elixir 脑图**：通过递归遍历 JSON 节点树，在微秒级内转化为带缩进的 Markdown 大纲。
  - **100% 离线隐私**：这两种解析不需要向任何第三方大模型上传文件，完全在您的本地沙箱执行，零 Token 成本，彻底阻绝隐私泄露。

### 痛点 4：隐私安全与大模型开销冲突 ( RAG )
* **现状**：想要将个人几十万字的笔记交给大模型做知识问答，但又极其抗拒将自己所有的日常日记、工作记录和密码资产直接暴露给云端 AI 厂商。
* **Prism 方案 (离线 QA & Prompt 编译器 - 自适应双通道召回)**：
  - 在 Sidecar 管理页面提供了一个高度隐私的本地 QA 离线问答面板。
  - **自适应双通道**：新增**“从向量库里取”**一键开关。勾选时，调用嵌入模型完成 Query 向量计算，走本地向量库语义检索（Semantic RAG）并配合严格的后置标签与逻辑关系（AND/OR）过滤器；未勾选或向量服务不可用时，平滑且无感降级为**“业务标签 + 正文模糊”双路精准召回**，并融合附件 Artifacts 解析大纲。
  - 后台拼接带有高保真参考上下文的**“超级 Prompt”**，提供“一键复制”动画按钮，把数据隐私控制权 100% 留给您。

---

## 🚀 核心功能大观

| 功能模块 | 业务表现 | 解决的痛点 | 融入日常工作流 |
| :--- | :--- | :--- | :--- |
| 🌈 **AI 智能整理** | 自动提取标题、生成结构化摘要、精炼核心要点、提取执行待办。 | 灵感杂乱无序、缺乏归纳和下一步行动指南。 | Memos 中保存随笔，1-2秒内侧栏自动生成 AI 归档卡片并原生双向引用。 |
| 🏷️ **双层标签治理** | 正式/候选标签物理隔离，标签总结支持 **临时提示词覆盖 (collapsible details)** 渲染生成。 | AI 滥发标签，标签分类散乱，总结提示词不便于按需在线实时调整。 | 新标签进入管理端等待审核；需要根据特定领域偏好生成总结时，一键展开临时提示词卡片直接覆盖。 |
| 💻 **本地离线解析** | 100% 本地离线解析 `.drawio` / `.drawio.svg` 和 `Mind Elixir JSON` 大纲。 | 附件图表内容不可读，无法被 AI 引用或索引。 | 直接将脑图、流程图传到 Memos 附件中，后台零开销秒转纯文本 Markdown 大纲。 |
| 🔍 **离线 RAG 编译器** | **向量库语义检索 (Semantic Search)** 与 **文本/标签精准检索** 自适应双通道召回。 | 担忧云端厂商泄露全部私密知识库，或不想承受昂贵的云端 RAG 托管费。 | 打开 QA 问答页面，一键勾选“从向量库里取”，输入问题即可复制专属于您的 RAG 上下文 Prompt。 |
| ⏰ **时间智能提醒** | 识别正文中自然语言，提取到期时间写入 SQLite，Bark (Webhook) 定时通知。 | 随手记下的待办事项，缺乏通知提醒导致遗忘。 | 写下 `#提醒 明天上午 10:00 提交周报`，时间一到，您的手机（iOS Bark）即刻弹出消息推送。 |
| 💾 **一键跨容器备份** | Memos 数据库 + 物理附件 + Sidecar 数据库 + 向量索引 + 配置文件一键全局热备份与恢复。 | 容器化部署在异地迁移、版本升级或多卷映射下备份极其繁琐。 | 执行 `backup.sh` 生成自包含压缩包，在别处解压运行 `restore.sh` 瞬间秒级异地完美搬家。 |

---


## 🔌 依赖的外部服务

Prism 需要以下外部服务才能正常运行核心 AI 功能。所有 API Key 通过环境变量注入，不写入配置文件或 Git 仓库。

### 🧠 推理大模型（必需）

AI 整理、标签总结、提醒抽取等核心功能依赖 OpenAI-compatible 推理大模型，默认使用 **DeepSeek**。支持以下 provider，可在 `config/models.yaml` 中切换或在管理页面实时修改：

| Provider | 默认模型 | 环境变量 | Base URL |
| :--- | :--- | :--- | :--- |
| **DeepSeek**（默认） | `deepseek-v4-flash` | `DEEPSEEK_API_KEY` | `https://api.deepseek.com` |
| OpenRouter | `google/gemma-3-27b-it` | `OPENROUTER_API_KEY` | `https://openrouter.ai/api/v1` |
| OpenAI | `gpt-4o-mini` | `OPENAI_API_KEY` | `https://api.openai.com/v1` |

> **至少配置一个 provider 的 API Key**，否则 AI 整理功能无法工作。推荐优先使用 DeepSeek（性价比高）或 OpenAI（准确性高）。

### 📐 嵌入大模型（默认开启）

向量语义检索功能依赖嵌入模型，**默认即开启**（`vector_search.enabled: true`）。当未配置嵌入 Key 时，Worker 会跳过向量入库，QA 面板自动降级为「业务标签 + 正文模糊」双路精准召回，不会影响主流程。

| Provider | 模型 | 环境变量 | Base URL |
| :--- | :--- | :--- | :--- |
| SiliconFlow | `BAAI/bge-m3` | `SILICONFLOW_API_KEY` | `https://api.siliconflow.cn/v1` |

如需关闭可在 `config/app.yaml` 或管理页面 `/admin/ui#vector-search` 中把 `vector_search.enabled` 设为 `false`；如需启用 RAG 增强问答只需配置 `SILICONFLOW_API_KEY` 环境变量。

### 📄 MinerU 文档解析（Office/PDF 附件）

`.doc`、`.docx`、`.xls`、`.xlsx`、`.ppt`、`.pptx`、`.pdf` 附件通过 MinerU 服务转为 Markdown 参与 AI 整理：

| 配置项 | 值 |
| :--- | :--- |
| 环境变量 | `MINERU_API_TOKEN` |
| Base URL | `https://mineru.net` |
| 模型版本 | `vlm`（可在 `config/app.yaml` 中修改 `document_parser.mineru_model_version`） |

> 不配置 `MINERU_API_TOKEN` 时，Office/PDF 附件将无法解析，但不影响纯文本、Draw.io、Mind Elixir 附件的处理。

## 📦 Docker 容器化一键部署与升级

为了保障在多租户 SaaS 部署、本地家庭网关等生产环境下的极简运维，Prism 现已支持 GitHub Actions 自动编译构建，并配备了完全自包含的一键部署脚本：

### 一键极速拉起步骤（全新部署 / 迁移）

在任何已安装 Docker 和 Bash 的宿主机（如本地 WSL2、家庭云服务器、公网 VPS）中，您仅需在打算存放数据的空目录下，执行以下一行命令即可：

```bash
# 执行自包含一键部署工具
bash <(curl -s -L https://raw.githubusercontent.com/nabule/Prism/master/deploy.sh)
```

**`deploy.sh` 脚本将在幕后全自动为您完成以下动作**：
1. **构建安全拓扑**：在当前目录下初始化 `config/`、`data/memos/`、`data/sidecar/`、`logs/caddy/` 等挂载文件夹。
2. **零人工干预配置**：若检测到没有网关配置，自动释放高性能边缘反代 `gateway/Caddyfile`，并生成初始 `config/app.yaml`。
3. **强密钥生成**：自动调用 OpenSSL 随机算法生成 **16 字节的超强随机 `SIDECAR_ADMIN_TOKEN`**，将其直接写入生成的 `.env` 文件中，默认即为最高防御状态。
4. **拉取与热启动**：执行 `docker compose -f docker-compose.release.yml pull` 从官方 Container Registry (GHCR) 一秒拉取 prebuilt 生产级镜像并热启动，在终端输出精美的彩色健康诊断信息。

---

## ⚡ 极速本地实机开发热重载配置

如果您是开发者，想要对源码进行快速二次开发和调试，**绝不需要反复进行昂贵的 `docker compose build` 镜像编译**：
* 映射本地源码 `./src` 到容器内 `/app/src`。
* 默认启用了 Uvicorn 自动重载监听（`--reload --reload-dir /app/src`）。
* 在 IDE 中直接编辑本地 `src/` 中的 Python 源码，容器内部的 Web 进程将在 **100 毫秒内热载生效**，**绝不需要频繁打镜像**。

---

## 🔒 多用户与安全隔离警示（多租户 SaaS 部署建议）

> [!WARNING]
> **多租户与隐私安全警示**：
> **Prism** 核心定位是**个人级离线 AI 知识库系统**。
> 单个 Sidecar 实例仅绑定单一的 `MEMOS_API_TOKEN`，且所有用户的附件解析大纲、智能标签建议和待处理任务全部共享集中存储于同一个 `sidecar.db` SQLite 数据库中。
> **请勿直接让多个独立用户共享使用同一个 Sidecar 实例**，否则在离线 QA 问答页面，用户提问的检索可能会发生跨账号的知识内容召回，带来**严重的隐私泄露与数据混淆风险**。

### 🚀 推荐的物理隔离方案（多租户物理沙箱）
若您需要为多人、家庭成员或团队成员部署，最安全、也是系统原生推荐的方式是**为每个账号部署物理隔离的容器栈**：
1. **目录隔离**：为每个用户在宿主机创建独立的部署工作目录，例如 `/data/prism_userA` 和 `/data/prism_userB`，下载相同的 `deploy.sh`。
2. **配置隔离**：在各自的 `.env` 中填写该用户专属的 `MEMOS_API_TOKEN`、`SIDECAR_ADMIN_TOKEN` 以及大模型的 API Key。
3. **端口隔离**：通过环境变量或 `.env` 修改各自网关对外暴露的 `GATEWAY_PORT` 端口（默认 `8085`；例如用户 A 设为 `8085`，用户 B 设为 `8086`）。
4. **统一反代**（可选）：使用宿主机的 Nginx 或 Caddy 将不同子域名（如 `user-a.memos.example.com` 和 `user-b.memos.example.com`）分别反向代理到对应的 `GATEWAY_PORT`，即刻享受到安全、物理层完全隔离防泄露的 SaaS 级多租户个人 AI 知识库体验。

---

## 👥 团队知识库（Team Knowledge Base）

在不放弃「个人沙箱」原则的前提下，Prism 新增了一层 **团队知识库** 能力：同一 `workspace_id` 内可以由管理员创建若干「团队」，每个团队拥有自己的成员、邀请码、词条集合和向量索引，互不串扰。它适合家庭成员协同收藏菜谱、研发小组维护事故复盘 Wiki、运营团队共建话术库等「需要少量人共享但不希望开放整库」的场景。

### 🧩 数据模型

| 表 | 关键字段 | 作用 |
| :--- | :--- | :--- |
| `teams` | `workspace_id` + `slug`（联合唯一）、`name`、`description` | 团队元信息，归属于 workspace |
| `team_members` | `team_id`、`role`（owner/editor/viewer）、`token_hash`（SHA-256） | 成员与访问令牌，明文 token 仅在创建/兑换瞬间返回一次 |
| `team_invites` | `code`、`role`、`max_uses`、`used_count`、`expires_at`、`revoked_at` | 邀请码生命周期管理 |
| `team_entries` | `team_id` + `uid`（联合唯一）、`title`、`body`、`tags_json`、`author_member_id` | 团队知识词条，编辑者隔离基于 `author_member_id` |
| `team_entry_vectors` | `entry_id`、`chunk_index`、`embedding_blob` | 词条向量分片，缺少嵌入 Key 时自动跳过 |

### 🔐 角色与令牌模型

* **管理员令牌（`SIDECAR_ADMIN_TOKEN`）**：携带该 token 调用任意 `/teams/...` 接口时，被视作「合成 owner」，可跨所有团队执行写操作，便于平台管理员兜底运维。
* **团队令牌（`team_xxx...`）**：成员加入团队后获得，前缀固定为 `team_`，数据库仅存 `sha256` 哈希。
* 角色排序：`owner > editor > viewer`。
  - **viewer**：只读检索、调用 QA Prompt。
  - **editor**：在 viewer 基础上可创建词条；**只能修改/删除自己创建的词条**（owner 与管理员可改任意词条）。
  - **owner**：可邀请、改角色、删词条、修改团队元信息。
* **最后一位 owner 保护**：当团队中只剩 1 名 owner 时，无法将其降级或移除，避免出现「无人能管理」的孤儿团队。

### 🛣️ REST 接口一览

| 方法 + 路径 | 鉴权 | 说明 |
| :--- | :--- | :--- |
| `POST /admin/teams` | 管理员 | 创建团队，返回团队信息 + 一次性 `owner_token` |
| `GET /admin/teams` | 管理员 | 列出 workspace 内全部团队 |
| `DELETE /admin/teams/{slug}` | 管理员 | 级联删除团队（成员、邀请、词条、向量一并清空） |
| `GET /teams/{slug}` | 团队成员 | 查看团队元信息与成员/词条计数 |
| `PUT /teams/{slug}` | owner | 修改团队名称、描述 |
| `GET /teams/{slug}/members` | 团队成员 | 列出成员（不含 token） |
| `PUT /teams/{slug}/members/{id}/role` | owner | 调整角色（受最后 owner 保护） |
| `DELETE /teams/{slug}/members/{id}` | owner | 移除成员（受最后 owner 保护） |
| `POST /teams/{slug}/invites` | owner | 生成邀请码（可设 `role` / `max_uses` / `expires_at`） |
| `GET /teams/{slug}/invites` | owner | 列出邀请记录（含已撤销/已耗尽） |
| `DELETE /teams/{slug}/invites/{id}` | owner | 撤销邀请码 |
| `POST /teams/join` | 公开（凭邀请码） | 兑换邀请码、设置展示名，返回一次性团队令牌 |
| `GET /teams/{slug}/entries` | 团队成员 | 列出词条，支持 `tag=`、`q=`、`limit/offset` 分页 |
| `POST /teams/{slug}/entries` | editor+ | 新建词条，标签自动去 `#` 前缀并去重 |
| `GET /teams/{slug}/entries/{uid}` | 团队成员 | 读取单条 |
| `PUT /teams/{slug}/entries/{uid}` | 作者本人 / owner / 管理员 | 编辑词条 |
| `DELETE /teams/{slug}/entries/{uid}` | 作者本人 / owner / 管理员 | 删除词条 |
| `POST /teams/{slug}/search` | 团队成员 | 语义/文本检索；`use_vector=true` 时调用嵌入模型，否则走 substring + 标签 |
| `POST /teams/{slug}/qa/generate-prompt` | 团队成员 | 组装「系统提示 + 团队参考上下文 + 用户提问」三段式超级 Prompt |

### 🚀 典型工作流

1. **管理员开团**：`POST /admin/teams` 提交 `slug` 与 `name`，返回的 `owner_token` 仅显示一次，请第一时间交给团队负责人。
2. **负责人邀请**：负责人持 `owner_token` 调用 `POST /teams/{slug}/invites`，按需设置 `role`（默认 `editor`）和 `max_uses`，把生成的 `code` 通过安全渠道分发。
3. **成员加入**：成员在前端或脚本中 `POST /teams/join`，提交邀请码和昵称，拿到属于自己的 `team_xxx` token。
4. **沉淀知识**：editor 通过 `POST /teams/{slug}/entries` 写入条目，标签可以带 `#` 也可以不带（统一存为去 `#` 的小写形式）；如果配置了 `SILICONFLOW_API_KEY`，每次写入会异步重建向量索引。
5. **检索/问答**：业务方调用 `/teams/{slug}/search` 做语义/文本检索；调用 `/teams/{slug}/qa/generate-prompt` 把检索到的条目自动拼接成超级 Prompt（与个人 RAG 接口同款渲染），最终把 Prompt 复制到任意大模型客户端即可获得答复。

### 🛡️ 安全与隔离要点

* 团队令牌与管理员令牌互不替代：团队令牌仅能访问自身所属团队的 `/teams/{slug}/...` 路径，跨团队调用直接 `403`。
* 邀请码支持 `max_uses=0`（无限次）、`expires_at`（过期失效）、`revoked_at`（手动撤销）三种终止条件，任一命中即拒绝兑换。
* 词条作者 ID 全程持久化，编辑/删除时会校验「调用者 == 作者」或「调用者为 owner/管理员」，避免横向越权。
* 缺少 `SILICONFLOW_API_KEY` 时，`/search` 与 `/qa/generate-prompt` 会自动降级为「substring + 标签」精准召回，行为与个人 RAG 面板的降级路径一致，不阻断主流程。
* 与个人 sidecar 一样，所有数据仍然保存在本地 `data/sidecar/sidecar.db`，没有任何团队内容会上传到第三方。

---

## 🛠️ 常用开发指令（Nx 集成管理）

所有底层依赖安装、编译、测试等任务均已深度封装，必须优先通过 `npx nx` 任务调度执行：

```bash
# 1. 运行全部单元测试（覆盖 RAG 拼装、提醒解析、Draw.io XML 离线解压缩）
npx nx test sidecar

# 2. 编译代码，检验 Python 语法及模块合规性
npx nx run sidecar:compile

# 3. 本地打包/重新编译 Docker 镜像
npx nx build sidecar

# 4. 运行 Memos API 状态与 Webhook 注册探针
npx nx run sidecar:probe-memos
```

---


## ⚙️ 配置项完整说明

所有配置通过三类文件管理，优先级：**环境变量 > `config/.env.local` > `config/*.yaml`**。

### 环境变量（`.env`）

部署前复制 `.env.example` 为 `.env` 并填写真实值。切勿提交包含密钥的 `.env` 到 Git。

| 变量 | 必需 | 说明 |
| :--- | :--- | :--- |
| `SIDECAR_ADMIN_TOKEN` | ✅ | Sidecar 管理接口 Bearer 令牌，建议 16 字节随机字符串（`deploy.sh` 会自动生成） |
| `MEMOS_BASE_URL` | ✅ | Memos 服务地址（如 `http://localhost:5230` 或 Docker 内 `http://memos:5230`） |
| `MEMOS_API_TOKEN` | ✅ | Memos Personal Access Token，推荐用探针生成长期 PAT |
| `MEMOS_WEBHOOK_URL` | ❌ | Memos 回调 Sidecar 的公网 URL（poll 模式下无需配置） |
| `DEEPSEEK_API_KEY` | ✅① | DeepSeek API Key（默认推理 provider） |
| `OPENROUTER_API_KEY` | ❌ | OpenRouter API Key（备选推理 provider） |
| `OPENAI_API_KEY` | ❌ | OpenAI API Key（备选推理 provider） |
| `MINERU_API_TOKEN` | ❌ | MinerU 文档解析 API Token（不配则 Office/PDF 附件跳过解析，纯文本/Draw.io/Mind Elixir 不受影响） |
| `SILICONFLOW_API_KEY` | ❌ | SiliconFlow API Key（向量检索默认开启，缺 Key 时自动跳过入库并降级到文本召回） |
| `REMINDER_WEBHOOK_URL` | ❌ | 提醒通知出口（Bark 兼容接口，如 `https://api.day.app/your-key/`） |
| `GATEWAY_PORT` | ❌ | Caddy 网关对外暴露端口，默认 `8085`（多租户部署时改为不同端口区分） |
| `PRISM_VERSION` | ❌ | 拉取 GHCR 镜像的版本标签，默认 `latest`，可锁定 `v0.6.6` 等确定版本 |

> ① 至少配置一个推理 provider 的 Key，推荐 `DEEPSEEK_API_KEY`。

### `config/app.yaml` — 应用主配置

| 配置路径 | 默认值 | 说明 |
| :--- | :--- | :--- |
| `app.workspace_id` | `default` | 工作区标识 |
| `app.public_base_url` | `http://localhost:8080` | Sidecar 对外公开地址 |
| `app.timezone` | `Asia/Shanghai` | Worker 进行提醒抽取、时区换算与日志时间显示使用的默认时区 |
| `database.path` | `data/sidecar/sidecar.db` | SQLite 数据库路径（WAL 模式） |
| `taxonomy.path` | `config/taxonomy.yaml` | 标签治理体系配置文件路径 |
| `prompts.path` | `config/prompts.yaml` | 提示词模板文件路径 |
| `memos.ingestion_mode` | `poll` | Memo 入口模式：`poll`（轮询）、`webhook`、`both` |
| `memos.poll_page_size` | `20` | 每次轮询拉取 memo 数量 |
| `memos.request_timeout_seconds` | `15` | Memos API 请求超时 |
| `memos.show_candidate_tags` | `false` | 是否在 Memos Web 中显示待审核标签 |
| `memos.admin_entry_enabled` | `true` | 是否自动维护管理入口 memo |
| `memos.admin_entry_title` | `Memosima 管理入口` | 管理入口 memo 标题 |
| `memos.admin_entry_visibility` | `PRIVATE` | 管理入口可见性：`PRIVATE` / `PUBLIC` |
| `document_parser.provider` | `mineru` | 文档解析 provider |
| `document_parser.base_url` | `https://mineru.net` | MinerU API 地址 |
| `document_parser.mineru_model_version` | `vlm` | MinerU 模型版本 |
| `document_parser.language` | `ch` | 解析语言 |
| `document_parser.timeout_seconds` | `60` | 单次任务超时（秒） |
| `document_parser.poll_interval_seconds` | `3` | 轮询 MinerU 批量解析结果间隔（秒） |
| `document_parser.max_polls` | `60` | 最多轮询次数，超时则视为失败 |
| `document_parser.enable_table` | `true` | 启用表格识别 |
| `document_parser.enable_formula` | `true` | 启用公式识别 |
| `document_parser.is_ocr` | `false` | 是否启用 OCR |
| `worker.poll_interval_seconds` | `2` | Worker 轮询新任务间隔 |
| `worker.max_attempts` | `3` | 任务最大重试次数 |
| `worker.create_probe_comment` | `false` | 是否在 Memos 中写入探针注释（仅排障时启用） |
| `reminders.enabled` | `true` | 是否启用提醒功能 |
| `reminders.trigger_tag` | `#提醒` | 提醒触发标签 |
| `reminders.confidence_threshold` | `0.75` | 提醒置信度阈值（低于该值会自动转为待澄清） |
| `reminders.request_timeout_seconds` | `10` | 调用 Bark/Webhook 通知出口的超时（秒） |
| `vector_search.enabled` | `true` | 是否启用向量检索（缺 Key 时自动跳过入库并平滑降级） |
| `vector_search.model` | `BAAI/bge-m3` | 嵌入模型名称 |
| `vector_search.base_url` | `https://api.siliconflow.cn/v1` | 嵌入服务 Base URL |
| `limits.max_attachment_mb` | `50` | 附件大小上限 (MB) |
| `limits.max_ai_active_tags` | `5` | AI 单次最多使用正式标签数 |
| `limits.max_ai_candidate_tags` | `2` | AI 单次最多提议候选标签数 |
| `limits.allowed_parse_extensions` | `.txt / .md / .doc(x) / .xls(x) / .ppt(x) / .pdf / .drawio / .drawio.svg / .json` | 允许进入附件解析流水线的后缀白名单 |

### `config/models.yaml` — 大模型 Provider 配置

定义可用的推理大模型 provider，结构如下（以 DeepSeek 为例）：

```yaml
default_provider: deepseek
providers:
  deepseek:
    base_url: https://api.deepseek.com
    api_key_env: DEEPSEEK_API_KEY        # 从环境变量读取 Key
    default_model: deepseek-v4-flash
    temperature: 0.2
    max_tokens: null
    response_format: json_object
```

可在管理页面 `/admin/ui#models` 实时切换 provider 和模型，保存后非机密参数写回 `config/models.yaml`，Key 写入 `config/.env.local`（不提交 Git）。

### `config/prompts.yaml` — AI 提示词模板

定义 `organize_memo`（整理 memo）、`tag_summary`（标签总结）、`reminder_extraction`（提醒提取）的 system/user 提示词，支持 `{active_tags}`、`{content}`、`{tag}` 等占位符。可在管理页面 `/admin/ui#prompts` 在线编辑并保存。

### `config/taxonomy.yaml` — 标签分类体系

定义系统标签、正式业务标签、别名映射和禁用标签。详见 [配置参数说明手册](https://nabule.github.io/Prism/配置说明.html)。

---

## 🌐 管理 REST API 速查表

所有 `/admin/*` 接口均要求请求头 `Authorization: Bearer ${SIDECAR_ADMIN_TOKEN}`；`/webhooks/memos` 与 `/health` 公开。完整字段、入参 schema、错误码定义请参见 [详细设计文档](https://nabule.github.io/Prism/详细设计.html) 的「管理 REST API 全量索引」章节。

| 分类 | 方法 + 路径 | 说明 |
| :--- | :--- | :--- |
| 健康 / 入口 | `GET /health` | 健康探针，返回版本与 worker 心跳。 |
| 健康 / 入口 | `GET /admin/ui` | 管理后台 SPA 单页（HTML）。 |
| Webhook | `POST /webhooks/memos` | Memos 推送新 memo 时的回调入口（幂等）。 |
| 任务 | `GET /admin/jobs` | 分页查询 Job 队列状态。 |
| 任务 | `POST /admin/jobs/{job_id}/retry` | 手动重试单个 Job。 |
| 任务 | `POST /admin/jobs/reprocess-memo` | 强制重新整理指定 memo。 |
| 任务 | `POST /admin/jobs/batch-reprocess-tag` | 按标签批量重排整理。 |
| 提示词 | `GET /admin/prompts` | 读取三类提示词模板。 |
| 提示词 | `PUT /admin/prompts/organize-memo` | 更新 organize-memo 模板并写回 `config/prompts.yaml`。 |
| 提示词 | `PUT /admin/prompts/tag-summary` | 更新 tag-summary 模板。 |
| 提示词 | `PUT /admin/prompts/reminder-extraction` | 更新 reminder-extraction 模板。 |
| 大模型 | `GET /admin/models` | 列出 provider/模型/连接性。 |
| 大模型 | `PUT /admin/models` | 切换默认 provider、模型，更新 `config/models.yaml`，Key 写入 `config/.env.local`。 |
| 标签 | `GET /admin/tag-candidates` | 列出待审核标签队列。 |
| 标签 | `POST /admin/tag-candidates/{id}/approve` | 通过候选标签并升级为正式业务标签。 |
| 标签 | `POST /admin/tag-candidates/{id}/reject` | 拒绝候选标签。 |
| 标签 | `GET /admin/tags/business` | 列出全部正式业务标签。 |
| 标签 | `POST /admin/tag-summaries` | 触发按标签生成专题总结（异步 Job）。 |
| 提醒 | `GET /admin/reminders` | 列出提醒（pending / sent / canceled / failed）。 |
| 提醒 | `POST /admin/reminders/{id}/retry` | 重新投递失败的提醒。 |
| 提醒 | `POST /admin/reminders/{id}/cancel` | 取消未发送的提醒。 |
| 提醒 | `GET/PUT /admin/reminders/config` | 读写提醒触发标签、置信度阈值、Webhook URL。 |
| 向量检索 | `GET/PUT /admin/vector-search/config` | 读写嵌入服务配置（Provider/Key/模型）。 |
| QA / RAG | `POST /admin/qa/generate-prompt` | 生成「超级 Prompt」（可选 `use_vector` 切换语义检索）。 |
| 文档解析 | `GET/PUT /admin/document-parser` | 配置 MinerU Token、模型版本、超时等。 |
| Memos 同步 | `GET/PUT /admin/memos/config` | 配置 Memos Base URL、PAT、可见性、入口模式。 |
| Memos 同步 | `POST /admin/memos/delete-all` | 危险操作：清空 Memos 主站全部 memo（仅排障）。 |
| 备份 / 恢复 | `GET /admin/backups/download` | 下载 ZIP 全局热备份（数据库 + 配置）。 |
| 备份 / 恢复 | `POST /admin/backups/restore` | 上传备份 ZIP 恢复。 |
| 数据库 | `POST /admin/database/reset` | 危险操作：删除并重建 sidecar SQLite。 |
| 日志 | `GET /admin/logs` | 查询结构化系统日志。 |
| 日志 | `POST /admin/logs/clear` | 清空系统日志表。 |

---

## 📄 关联项目文档

* [📘 详细设计文档 🌐](https://nabule.github.io/Prism/详细设计.html) - **新增**：面向二次开发的全链路架构、模块边界、数据库 schema、任务生命周期、API 索引、扩展指引。
* [普通用户工作流指南 🌐](https://nabule.github.io/Prism/普通用户使用手册.html) - 指引普通用户如何将 Prism 折射库无缝融入日常记录中，说明各功能用途与工作流结合。
* [使用手册 (部署与运维) 🌐](https://nabule.github.io/Prism/使用手册.html) - 系统管理员多容器拓扑部署、极速开发热载、与 Nx 任务管理指南。
* [团队知识库使用手册 📄](./docs/团队知识库使用手册.html) - 从开团、邀请、加入、写词条到检索/生成 RAG Prompt 的完整 curl 走查、权限矩阵、错误码与运维建议。
* [配置参数说明手册 🌐](https://nabule.github.io/Prism/配置说明.html) - `app.yaml` 静态配置体系及环境变量安全秘钥管理指引。

### 💻 架构、设计与探针记录
* [开发运行说明 🌐](https://nabule.github.io/Prism/开发运行说明.html) - 面向二次开发人员的本地调试、API 路由、以及核心架构说明。
* [API 探针记录 🌐](https://nabule.github.io/Prism/API探针记录.html) - 针对 Memos 官方 API 接口的捕获、分析与探针运行测试结论。
* [PRD 个人 AI 知识库系统说明书 🌐](https://nabule.github.io/Prism/PRD-个人AI知识库系统.html) - 系统底层需求规格说明书与设计愿景。
* [基于 Memos 详细设计与开发计划 🌐](https://nabule.github.io/Prism/基于-Memos-的个人-AI-知识库系统详细设计与开发计划.html) - 后台同步、AI 归档的详细数据库及生命周期设计。
* [开发计划与验收标准 🌐](https://nabule.github.io/Prism/开发计划与验收标准-个人AI知识库系统.html) - 项目里程碑、验收要点与交付规范记录。
* [技术架构设计 🌐](https://nabule.github.io/Prism/技术架构设计-个人AI知识库系统.html) - Prism 全链路时序、并发、持久化底层架构。
