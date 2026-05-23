# Caddy 统一入口发布实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 为 Memosima 增加 Caddy 网关统一入口，默认只暴露一个 Compose 入口，并发布 `0.2.0`。

**架构：** Docker Compose 新增 `gateway` 服务，使用 Caddy 按路径代理到内部的 `memos:5230` 和 `sidecar:8080`。Sidecar 与 worker 仍通过内部网络访问 Memos，用户和管理链接统一访问网关地址。

**技术栈：** Docker Compose、Caddy、Nx、uv、pytest、Python。

---

## 文件职责

- 创建：`gateway/Caddyfile`。定义统一入口路由。
- 创建：`tests/test_deployment.py`。静态解析 Compose 与 Caddyfile，覆盖默认部署约束。
- 修改：`docker-compose.yml`。新增 `gateway`，收敛宿主机端口。
- 修改：`sidecar/project.json`。让 `build` 覆盖完整 Compose 发布构建。
- 修改：`pyproject.toml`、`uv.lock`、`src/memosima/__init__.py`、`Dockerfile`。发布版本升到 `0.2.0`。
- 修改：`README.html`、`docs/使用手册.html`、`docs/普通用户使用手册.html`、`docs/配置说明.html`、`docs/开发运行说明.html`、`技术架构设计-个人AI知识库系统.html`、`开发计划与验收标准-个人AI知识库系统.html`。同步部署入口和发布说明。

### 任务 1：部署配置测试

**文件：**
- 创建：`tests/test_deployment.py`

- [ ] **步骤 1：编写失败的测试**

```python
from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def _compose() -> dict:
    return yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))


def _caddyfile() -> str:
    return (ROOT / "gateway" / "Caddyfile").read_text(encoding="utf-8")


def test_compose_exposes_only_gateway_port_by_default():
    services = _compose()["services"]

    assert "gateway" in services
    assert services["gateway"]["image"] == "xget.your-domain.com/cr/docker/library/caddy:2.10.2"
    assert services["gateway"]["ports"] == ["${GATEWAY_PORT:-8080}:80"]
    assert "ports" not in services["memos"]
    assert "ports" not in services["sidecar"]


def test_caddy_routes_sidecar_paths_and_memos_root():
    caddyfile = _caddyfile()

    assert "handle /admin/*" in caddyfile
    assert "handle /health" in caddyfile
    assert "handle /webhooks/*" in caddyfile
    assert caddyfile.count("reverse_proxy sidecar:8080") >= 3
    assert "reverse_proxy memos:5230" in caddyfile
```

- [ ] **步骤 2：运行测试验证失败**

运行：`npx nx test sidecar -- tests/test_deployment.py -q`

预期：失败。失败原因是 `gateway/Caddyfile` 不存在或 Compose 中没有 `gateway` 服务。

### 任务 2：实现 Caddy 网关配置

**文件：**
- 创建：`gateway/Caddyfile`
- 修改：`docker-compose.yml`
- 修改：`sidecar/project.json`

- [ ] **步骤 1：创建 Caddyfile**

```caddyfile
:80 {
	handle /admin/* {
		reverse_proxy sidecar:8080
	}

	handle /health {
		reverse_proxy sidecar:8080
	}

	handle /webhooks/* {
		reverse_proxy sidecar:8080
	}

	handle {
		reverse_proxy memos:5230
	}
}
```

- [ ] **步骤 2：更新 Compose**

将 `docker-compose.yml` 调整为：

```yaml
services:
  gateway:
    image: xget.your-domain.com/cr/docker/library/caddy:2.10.2
    container_name: memosima-gateway
    restart: unless-stopped
    depends_on:
      - memos
      - sidecar
    ports:
      - "${GATEWAY_PORT:-8080}:80"
    volumes:
      - ./gateway/Caddyfile:/etc/caddy/Caddyfile:ro
      - ./data/caddy:/data
      - ./logs/caddy:/var/log/caddy

  memos:
    image: xget.your-domain.com/cr/docker/neosmemo/memos:stable
    container_name: memosima-memos
    restart: unless-stopped
    volumes:
      - ./data/memos:/var/opt/memos
    environment:
      MEMOS_PORT: 5230
      MEMOS_DRIVER: sqlite

  sidecar:
    build: .
    container_name: memosima-sidecar
    restart: unless-stopped
    depends_on:
      - memos
    env_file:
      - .env
    environment:
      MEMOS_BASE_URL: http://memos:5230
    volumes:
      - ./config:/app/config
      - ./data/sidecar:/app/data/sidecar
      - ./logs:/app/logs
    command: uvicorn memosima.api.app:create_app --factory --host 0.0.0.0 --port 8080

  sidecar-worker:
    build: .
    container_name: memosima-sidecar-worker
    restart: unless-stopped
    depends_on:
      - memos
      - sidecar
    env_file:
      - .env
    environment:
      MEMOS_BASE_URL: http://memos:5230
    volumes:
      - ./config:/app/config
      - ./data/sidecar:/app/data/sidecar
      - ./logs:/app/logs
    command: memosima-worker
```

- [ ] **步骤 3：更新 Nx build target**

将 `sidecar/project.json` 的 `build.options.command` 改为：

```json
"docker compose build"
```

- [ ] **步骤 4：运行部署配置测试验证通过**

运行：`npx nx test sidecar -- tests/test_deployment.py -q`

预期：2 passed。

### 任务 3：发布版本号

**文件：**
- 修改：`pyproject.toml`
- 修改：`uv.lock`
- 修改：`src/memosima/__init__.py`
- 修改：`Dockerfile`

- [ ] **步骤 1：更新版本字符串**

把四处 `0.1.1` 改为 `0.2.0`：

```text
pyproject.toml
uv.lock
src/memosima/__init__.py
Dockerfile
```

- [ ] **步骤 2：运行版本相关测试**

运行：`npx nx test sidecar -- tests/test_config.py tests/test_api.py -q`

预期：相关测试通过。

### 任务 4：更新文档

**文件：**
- 修改：`README.html`
- 修改：`docs/使用手册.html`
- 修改：`docs/普通用户使用手册.html`
- 修改：`docs/配置说明.html`
- 修改：`docs/开发运行说明.html`
- 修改：`技术架构设计-个人AI知识库系统.html`
- 修改：`开发计划与验收标准-个人AI知识库系统.html`

- [ ] **步骤 1：替换默认入口说明**

将默认访问入口统一写为：

```text
http://localhost:8080/
http://localhost:8080/admin/ui
http://localhost:8080/health
```

说明 `5230` 和 Sidecar 内部 `8080` 默认不直接暴露到宿主机。

- [ ] **步骤 2：补充 Caddy 网关说明**

文档中明确：

```text
Docker Compose 默认包含 gateway、memos、sidecar、sidecar-worker 四个服务。
gateway 使用 Caddy 按路径分流：/admin/*、/health、/webhooks/* 到 Sidecar，其余路径到 Memos。
可通过 GATEWAY_PORT 修改宿主机端口，例如 GATEWAY_PORT=8090 npx nx run sidecar:up。
```

- [ ] **步骤 3：运行文档关键字检查**

运行：`rg -n "localhost:5230|localhost:8080/admin/ui|Caddy|gateway|GATEWAY_PORT" README.html docs 技术架构设计-个人AI知识库系统.html 开发计划与验收标准-个人AI知识库系统.html`

预期：`localhost:5230` 不再作为默认入口出现；`Caddy`、`gateway`、`GATEWAY_PORT` 有说明。

### 任务 5：完整验证与发布提交

**文件：**
- 检查全部变更

- [ ] **步骤 1：运行完整测试**

运行：`npx nx test sidecar`

预期：全部测试通过，输出包含通过数量。

- [ ] **步骤 2：运行编译**

运行：`npx nx run sidecar:compile`

预期：exit 0。

- [ ] **步骤 3：运行 Docker 构建**

运行：`npx nx build sidecar`

预期：gateway 镜像可拉取，sidecar 和 sidecar-worker 构建成功。

- [ ] **步骤 4：启动真实 Compose 栈**

运行：`npx nx run sidecar:up`

预期：`gateway`、`memos`、`sidecar`、`sidecar-worker` 运行。

- [ ] **步骤 5：验证真实统一入口**

运行：

```bash
curl -fsS http://localhost:8080/ -o /tmp/memosima-memos.html
curl -fsS http://localhost:8080/admin/ui -o /tmp/memosima-admin.html
curl -fsS http://localhost:8080/health
```

预期：

- `/tmp/memosima-admin.html` 包含 `Memosima`。
- `/health` 返回 JSON，包含 `version`、`workspace_id`。
- Memos 根路径返回 HTTP 200 或可识别的 Memos Web HTML。

- [ ] **步骤 6：提交前机密检查**

运行：

```bash
git diff | rg -n "(api[_-]?key|secret|token|password|passwd|Authorization|Bearer|sk-[A-Za-z0-9]|ghp_|github_pat_|AKIA|BEGIN (RSA|OPENSSH|PRIVATE) KEY)"
git status --short
```

预期：只出现字段名、环境变量名、文档占位符或测试假值；不出现真实密钥。

- [ ] **步骤 7：中文提交**

运行：

```bash
git add gateway/Caddyfile docker-compose.yml sidecar/project.json pyproject.toml uv.lock src/memosima/__init__.py Dockerfile tests/test_deployment.py README.html docs/使用手册.html docs/普通用户使用手册.html docs/配置说明.html docs/开发运行说明.html 技术架构设计-个人AI知识库系统.html 开发计划与验收标准-个人AI知识库系统.html docs/superpowers/specs/2026-05-23-caddy-gateway-release-design.md docs/superpowers/plans/2026-05-23-caddy-gateway-release.md
git commit -m "feat(部署): 增加 Caddy 统一入口网关"
```

提交正文写明：

```text
- 新增 Caddy gateway 服务，统一代理 Memos 与 Sidecar。
- 默认只暴露 GATEWAY_PORT，Memos 与 Sidecar 端口改为内部访问。
- 更新发布版本到 0.2.0。
- 更新部署、配置、使用和架构文档。

验证：
- npx nx test sidecar
- npx nx run sidecar:compile
- npx nx build sidecar
- npx nx run sidecar:up
- curl http://localhost:8080/
- curl http://localhost:8080/admin/ui
- curl http://localhost:8080/health
```
