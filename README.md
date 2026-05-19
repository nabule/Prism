# Memosima

Memosima 是基于 Memos 的个人 AI 知识库 Sidecar 服务。当前代码处于 P0+P1 阶段，目标是完成项目骨架、Memos Webhook 接入、SQLite 任务系统和真实联调探针。

## 本地开发

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
cp .env.example .env
pytest
```

启动 API：

```bash
uvicorn memosima.api.app:create_app --factory --host 0.0.0.0 --port 5230
```

启动 worker：

```bash
memosima-worker --once
```

## 配置

- `SIDECAR_ADMIN_TOKEN`：管理接口 Bearer token。
- `MEMOS_BASE_URL`：Memos 服务地址。
- `MEMOS_API_TOKEN`：Memos API token。
- `OPENROUTER_API_KEY`：OpenRouter API key，仅通过环境变量配置，不提交到仓库。

更多说明见 [docs/配置说明.md](docs/配置说明.md)。

