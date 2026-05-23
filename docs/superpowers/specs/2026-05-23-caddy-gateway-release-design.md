# Caddy 统一入口发布设计

## 背景

当前 Docker Compose 同时把 Memos 暴露到宿主机 `5230`，把 Sidecar API 暴露到 `8080`。用户需要记住两个入口，Memos 内的管理链接也指向 Sidecar 单独端口。目标是在默认部署中提供一个统一入口，由网关按路径把请求转发到 Memos 或 Sidecar，并交付可直接发布的 Docker Compose 部署文件。

## 目标

- 默认部署只暴露一个宿主机入口：`http://localhost:8080`。
- `http://localhost:8080/` 进入 Memos。
- `http://localhost:8080/admin/ui`、`/admin/*`、`/health`、`/webhooks/*` 进入 Sidecar。
- Memos 和 Sidecar 容器保留内部端口，但默认不直接映射到宿主机。
- Sidecar 生成的管理链接使用统一入口。
- 版本发布到 `0.2.0`，并更新 README、使用、配置、开发运行和架构/设计文档。

## 非目标

- 不把 Memos 放到 `/memos/` 子路径。
- 不在 Sidecar 应用内实现 Memos 代理。
- 不在本次引入 HTTPS 自动证书、域名配置或多租户路由。
- 不要求 Memos webhook 在本地私网地址下绕过 Memos 0.28 的安全限制；默认仍推荐轮询模式。

## 方案

新增 Caddy 网关容器：

- 服务名：`gateway`
- 镜像：`xget.your-domain.com/cr/docker/library/caddy:<固定版本>`
- 配置文件：`gateway/Caddyfile`
- 端口映射：`${GATEWAY_PORT:-8080}:80`
- 依赖：`memos`、`sidecar`

Caddyfile 使用同域路径分流：

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

`docker-compose.yml` 调整：

- `memos` 移除 `ports`，只在 Compose 网络内提供 `5230`。
- `sidecar` 移除 `ports`，只在 Compose 网络内提供 `8080`。
- `gateway` 挂载 `./gateway/Caddyfile:/etc/caddy/Caddyfile:ro`。
- `sidecar` 和 `sidecar-worker` 继续使用 `MEMOS_BASE_URL=http://memos:5230`。

`config/app.yaml` 调整：

- `app.public_base_url` 保持统一入口默认值 `http://localhost:8080`。

Nx target 调整：

- `build` 改为 `docker compose build`，确保发布构建覆盖完整栈。
- `up` 保持 `docker compose up -d`，启动完整栈。

## 测试与验收

静态和单元验证：

- 新增测试读取 `docker-compose.yml` 和 `gateway/Caddyfile`，断言：
  - Compose 定义 `gateway` 服务。
  - `gateway` 使用 Xget Caddy 镜像。
  - `gateway` 暴露 `${GATEWAY_PORT:-8080}:80`。
  - `memos` 和 `sidecar` 默认没有 `ports`。
  - Caddyfile 将 `/admin/*`、`/health`、`/webhooks/*` 转发到 `sidecar:8080`。
  - 默认路由转发到 `memos:5230`。

真实验证：

- `npx nx test sidecar`
- `npx nx run sidecar:compile`
- `npx nx build sidecar`
- `npx nx run sidecar:up`
- 从实际监听端口访问：
  - `GET http://localhost:8080/` 返回 Memos 入口响应。
  - `GET http://localhost:8080/admin/ui` 返回 Sidecar 管理页 HTML，包含 `Memosima` 或管理页关键 DOM。
  - `GET http://localhost:8080/health` 返回 Sidecar health JSON。

## 文档

需要同步更新：

- `README.html`
- `docs/使用手册.html`
- `docs/普通用户使用手册.html`
- `docs/配置说明.html`
- `docs/开发运行说明.html`
- `技术架构设计-个人AI知识库系统.html`
- `开发计划与验收标准-个人AI知识库系统.html`

文档中应明确默认入口从 Sidecar 直连变为 Caddy 统一入口，`5230` 和 Sidecar 内部 `8080` 不再作为默认宿主机入口。

## 发布

本次发布版本为 `0.2.0`，更新：

- `pyproject.toml`
- `uv.lock`
- `src/memosima/__init__.py`
- `Dockerfile` 中安装依赖阶段的临时版本号

提交前必须检查 diff，确认没有真实 `.env`、API key、token、cookie、私钥或内网敏感地址进入 git。
