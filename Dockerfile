FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app
ENV UV_LINK_MODE=copy
ENV UV_PROJECT_ENVIRONMENT=/app/.venv
ENV PATH="/app/.venv/bin:${PATH}"

COPY pyproject.toml uv.lock README.html ./
RUN mkdir -p src/memosima && printf '__version__ = "0.6.2"\\n' > src/memosima/__init__.py
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
RUN uv sync --frozen --no-dev

COPY config ./config
CMD ["uvicorn", "memosima.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080"]
