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
- Webhook payload 可能随 Memos 版本变化，因此 Sidecar 对 `memo.uid`、`memo.id`、`memo.name`、顶层 `memoUid` 等字段做兼容提取。

## 本机真实探针状态

当前 Linux 环境执行结果：

```text
Docker version 29.5.1
Docker Compose version v5.1.3
```

Docker 已可用，但镜像拉取仍受外部网络限制：

```text
Docker Hub: i/o timeout
Xget Docker Hub mirror: 429 Too Many Requests
Xget GHCR mirror: 429 Too Many Requests
```

Docker Hub/GHCR 镜像已按 Xget 规则改用 `xget.xi-xu.me/cr/...` 加速地址。当前阻塞为 Xget 限流，非本地 Docker 安装问题。

因此 P0 的真实 Memos 容器联调尚未完成。代码已具备 webhook 接收、任务落库、worker 拉取 memo 和可选探针评论能力；需要在镜像可拉取或提供远程 Memos 实例后执行真实验收。

## 待执行真实探针

1. 启动 Memos 和 Sidecar。
2. 创建 Memos 管理员和 API token。
3. 在 Memos 配置 webhook 指向 `POST /webhooks/memos`。
4. 手动创建一条 memo。
5. 确认 Sidecar 创建 `process_memo` 任务。
6. 运行 worker。
7. 确认 worker 能读取真实 memo 并标记任务成功。
8. 如开启 `worker.create_probe_comment`，确认原 memo 下出现 P0 探针评论。
