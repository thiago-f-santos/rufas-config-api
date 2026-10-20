FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim AS builder
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=0
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev
COPY data ./data
RUN .venv/bin/python -m rufas_config_api.providers.soil.index --data-dir data/soil --output data/soil/soil_catalog.sqlite

FROM python:3.14-slim-bookworm
RUN useradd --create-home app
WORKDIR /app
COPY --from=builder --chown=app:app /app /app
ENV PATH="/app/.venv/bin:$PATH"
USER app
EXPOSE 8000
CMD ["uvicorn", "rufas_config_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
