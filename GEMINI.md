## 这是AI驱动的知识库程序

**你所有的回复必须用中文**

0. 读取工程中的文档，获取背景信息，更新程序后要及时跟新文档。
1. 所有git提交要带有中文信息，详细说明内容。按功能提交。
2. 在WSL中开发和测试
3. 完成的代码必须经过完整的测试验证
4. 所有依赖安装、测试、构建和常用开发命令必须优先通过 `npx nx ...` 这类项目任务入口执行；不要直接运行 `pip install` 或在文档中要求直接使用 pip。Python 包和虚拟环境统一使用 `uv` 管理，并封装在 Nx target、容器构建或后续统一脚本中。
5. 项目中所有第三方公共镜像（如 Caddy、Memos、uv 运行底座等）统一使用官方源（如 Docker Hub、GHCR），不再使用任何 Xget 镜像加速方案。
6. 开发阶段优先下载/查看源码、实现本地代码并通过 `npx nx test ...` 验证；Docker 构建和 Compose 联调放在阶段末尾做验收，不作为每次小改动的中途验证。
7. 部署测试、Compose 联调和用户验收前必须确认运行的是最新代码：先完成必要的构建或源码启动，确认容器/进程未使用旧镜像、旧挂载或旧进程，再从运行中的容器或实际监听端口访问接口和页面做结论。不能只根据本地源码、测试通过或镜像构建成功判断部署已更新；涉及管理页面变更时，必须验证已部署页面包含本次新增/修改的关键文案或 DOM。
8. 严禁向 git 提交任何机密信息，包括但不限于 API key、access token、Personal Access Token、密码、私钥、真实 `.env`、cookie、会话信息、内网敏感地址以及用户的私有域名等。提交前必须检查 diff，确认只包含占位符、示例值或已脱敏内容；如误写入机密，应先移除并通过 `git reset --hard` 或重写 Git 历史彻底抹除，并通知用户。
9. 本地部署测试时，禁止通过 Docker 启动进行验证——Docker 容器使用的是构建时的镜像快照，修改源码后若不重新构建镜像，容器内运行的仍是旧代码，极易误判"改动未生效"或"已修复的 bug 仍在"；必须使用 `npx nx serve ...` 或直接通过 `uv run` / 项目脚本以源码方式启动服务，确保每次验证运行的都是最新代码。

### Code Search

优先使用 `semble search` 按语义查找代码片段，适合描述目标行为、模块职责或符号名；只有在需要精确字面量匹配、日志文本、注释文本或穷举确认时再使用 `rg`。本机 Semble 通过 `uv tool install --upgrade "semble[mcp]"` 安装和更新，当前 CLI 支持 `search` 与 `find-related` 两个核心检索能力。

```bash
semble search "authentication flow" .
semble search -k 10 "save model to disk" . --content code
semble search -k 10 "deployment guide" . --content all
```

使用 `semble find-related` 基于已有搜索结果中的文件路径和行号查找相似实现：

```bash
semble find-related -k 5 src/auth.py 42 . --content code
```

`path` 省略时默认为当前目录，也可以传入 Git URL。`--content` 可选 `code`、`docs`、`config`、`all`，默认 `code`；不要再使用已弃用的 `--include-text-files`。若当前环境找不到 `semble`，使用 `uvx --from "semble[mcp]" semble` 代替。

项目内提供自动更新并检索的脚本：

```bash
scripts/semble_refresh_search.sh search "Memos API client" . 5 code
scripts/semble_refresh_search.sh find-related src/memosima/memos/probe.py 35 . 5 code
```

脚本默认会先执行 `uv tool install --upgrade "semble[mcp]"`，再运行检索；如只想使用现有版本，设置 `SEMBLE_SKIP_UPGRADE=1`。

推荐流程：

1. 先用 `scripts/semble_refresh_search.sh search` 或 `semble search` 获取相关代码片段。
2. 只有返回片段不足以判断时，再打开完整文件。
3. 对有代表性的结果使用 `scripts/semble_refresh_search.sh find-related` 或 `semble find-related` 查找相似实现。
4. 仅在需要精确字面量匹配或穷举确认时使用 `rg`。

### 自动化通知协议 (Notification Protocol)

当满足以下任一条件时，**必须**执行 All Notify 通知指令，通知指令直接执行无需等待用户确认：

1. 一个主要子任务 (Sub-task) 已完成。
2. 任务挂起，等待用户提供输入或确认。
3. 生成任何报告（如代码审查、安全审查、测试报告等）。

统一通过本地私有配置中的 All Notify 入口发送，禁止直接调用 Bark、SMTP 等下游通道。真实入口不要写入 Git；可保存在 `.codex/local-notify.md` 等已忽略的本地文件中。

**GET 指令模板:**

```bash
title="任务更新" # 根据上下文修改标题
body="当前任务已完成/等待输入..." # 根据上下文修改内容

curl -sS -G "$ALL_NOTIFY_URL" \
     --data-urlencode "title=$title" \
     --data-urlencode "message=$body" \
     -o /dev/null
```

**POST JSON 指令模板（适合长内容/报告）:**

```bash
curl -sS -X POST "$ALL_NOTIFY_URL" \
     -H "Content-Type: application/json" \
     -d '{"title":"任务更新","message":"当前任务已完成"}' \
     -o /dev/null
```
