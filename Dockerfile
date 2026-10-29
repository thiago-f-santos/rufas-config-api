FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim AS builder
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=0
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY README.md alembic.ini ./
COPY alembic ./alembic
COPY src ./src
RUN uv sync --frozen --no-dev
COPY data ./data

FROM python:3.14-slim-bookworm
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 postgresql-client \
    && rm -rf /var/lib/apt/lists/*
RUN useradd --create-home app
WORKDIR /app
COPY --from=builder --chown=app:app /app /app
RUN printf '#!/bin/sh\nset -e\nalembic upgrade head\nexec "$@"\n' > /entrypoint.sh \
    && chmod +x /entrypoint.sh
ENV PATH="/app/.venv/bin:$PATH"
USER app
EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "rufas_config_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
