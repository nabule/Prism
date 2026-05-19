# API 探针记录

## 官方资料

- Memos API latest: https://usememos.com/docs/api/latest
- Memos Webhooks: https://usememos.com/docs/integrations/webhooks
- Memos Docker 部署: https://usememos.com/docs/deploy/docker
- OpenRouter OpenAI-compatible API: https://openrouter.ai/docs

## 当前实现假设

- Memos API 通过 `/api/v1` 暴露。
- 读取 memo 使用 `GET /api/v1/memos/{uid}`。
- 创建 memo 使用 `POST /api/v1/memos`。
- 创建评论使用 `POST /api/v1/memos/{memo_uid}/comments`。
- 当前用户使用 `GET /api/v1/auth/me`。
- 用户 webhook 使用 `GET/POST/PATCH/DELETE /api/v1/users/{username}/webhooks`。
- Webhook payload 可能随 Memos 版本变化，因此 Sidecar 对 `memo.uid`、`memo.id`、`memo.name`、顶层 `memoUid` 等字段做兼容提取。

## 本机真实探针状态

当前 Linux 环境执行结果：

```text
Docker version 29.5.1
Docker Compose version v5.1.3
```

Docker 已可用。镜像拉取验证记录：

```text
Docker Hub: i/o timeout
xget.xi-xu.me Docker Hub mirror: 429 Too Many Requests
xget.xi-xu.me GHCR mirror: 429 Too Many Requests
xget.your-domain.com Docker Hub mirror: 拉取 Memos 成功
xget.your-domain.com GHCR mirror: 构建 Sidecar 成功
```

Docker Hub/GHCR 镜像已按 Xget 规则改用 `xget.your-domain.com/cr/...` 加速地址。

P0 的真实 Memos 容器联调已跑通手动 webhook 投递路径：真实 Memos memo 创建成功，Sidecar 接收 webhook 后创建任务，worker 使用真实 Memos API 读取 memo 并写入 `memos` 映射表。

Memos 内置 webhook 管理接口已验证：

```text
GET /api/v1/users/test/webhooks -> {"webhooks":[]}
POST /api/v1/users/test/webhooks {"url":"https://example.com/memosima-webhook","displayName":"Memosima Sidecar Test"}
-> {"name":"users/test/webhooks/...","url":"https://example.com/memosima-webhook","displayName":"Memosima Sidecar Test",...}
DELETE /api/v1/users/test/webhooks/...
```

同时确认 Memos `0.28.0` 会拒绝 webhook URL 解析到 Docker 内网或保留/私有 IP：

```text
POST /api/v1/users/test/webhooks {"url":"http://sidecar:8080/webhooks/memos",...}
-> 400 webhook URL must not resolve to a reserved or private IP address
```

因此自动回调验收需要 `MEMOS_WEBHOOK_URL` 指向公网可达的 Sidecar URL，或通过公网隧道转发到本机 `http://localhost:8080`。

## 待执行真实探针

1. 启动 Memos 和 Sidecar。
2. 创建 Memos 管理员和 API token。
3. 使用 `npx nx run sidecar:probe-memos -- --configure-webhook-url "$MEMOS_WEBHOOK_URL"` 配置 Memos 用户 webhook。
4. 手动创建一条 memo。
5. 确认 Sidecar 创建 `process_memo` 任务。
6. 运行 worker。
7. 确认 worker 能读取真实 memo 并标记任务成功。
8. 如开启 `worker.create_probe_comment`，确认原 memo 下出现 P0 探针评论。

可使用一条命令完成“配置 webhook -> 创建 memo -> 轮询 Sidecar jobs”的自动探针：

```bash
npx nx run sidecar:probe-memos -- \
  --bootstrap-username test \
  --bootstrap-password testtest \
  --configure-webhook-url "$MEMOS_WEBHOOK_URL" \
  --create-memo "自动 webhook 探针 #系统/原始记录" \
  --verify-sidecar-url "http://localhost:8080" \
  --verify-sidecar-token "$SIDECAR_ADMIN_TOKEN"
```

## 自动 webhook 真实验收（2026-05-19）

已使用 `cloudflared` 临时公网隧道暴露本机 Sidecar：

```text
https://goat-pest-drum-lips.trycloudflare.com -> http://localhost:8080
```

验收前通过 Nx 探针创建 Memos Personal Access Token，并以临时 env 文件注入 Sidecar/worker 容器，避免 worker 使用会过期的登录 access token。

执行命令：

```bash
npx nx run sidecar:probe-memos -- \
  --bootstrap-username test \
  --bootstrap-password testtest \
  --configure-webhook-url "https://goat-pest-drum-lips.trycloudflare.com/webhooks/memos" \
  --webhook-display-name "Memosima Sidecar Tunnel" \
  --create-memo "自动 webhook PAT 验收 2026-05-19T16:16:21+08:00 #系统/原始记录" \
  --verify-sidecar-url "http://localhost:8080" \
  --verify-sidecar-token "$SIDECAR_ADMIN_TOKEN" \
  --verify-timeout-seconds 60
```

结果：

```text
created_memo: memos/aJMxBAuM2SpAdcZsQd4dPe
webhook_action: unchanged
sidecar_verification.status: succeeded
sidecar job id: 3
worker: GET http://memos:5230/api/v1/memos/aJMxBAuM2SpAdcZsQd4dPe -> 200 OK
```

这次验收确认 Memos 内置 webhook 自动回调 Sidecar、Sidecar 创建 `process_memo` 任务、worker 使用真实 Memos API 读取 memo 并将任务标记为 `succeeded`。
