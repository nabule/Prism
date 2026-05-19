FROM xget.your-domain.com/cr/ghcr/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app
ENV UV_LINK_MODE=copy
ENV UV_PROJECT_ENVIRONMENT=/app/.venv
ENV PATH="/app/.venv/bin:${PATH}"

COPY pyproject.toml README.md ./
COPY src ./src
RUN uv sync --no-dev

COPY config ./config
CMD ["uvicorn", "memosima.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080"]
