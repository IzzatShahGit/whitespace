# Build context: repository root (the API depends on the shared/ package).
#   docker build -f backend/Dockerfile .

# ---------- build ----------
FROM ghcr.io/astral-sh/uv:0.9-python3.12-bookworm-slim AS build
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app

# Dependencies first, so code changes don't reinstall them.
COPY pyproject.toml uv.lock ./
COPY backend/pyproject.toml backend/
COPY pipeline/pyproject.toml pipeline/
COPY shared/pyproject.toml shared/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --package whitespace-api --no-install-workspace

COPY shared shared
COPY backend backend
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --package whitespace-api --no-editable

# ---------- runtime ----------
FROM python:3.12-slim-bookworm AS runtime
RUN useradd --create-home --uid 1000 app
WORKDIR /app
COPY --from=build --chown=app:app /app/.venv /app/.venv
COPY --chown=app:app backend/alembic.ini ./backend/alembic.ini
COPY --chown=app:app backend/migrations ./backend/migrations
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health')"
# One process on purpose: AI key rotation and background jobs live in its memory.
# On stop, in-flight briefs and chat replies get 25 s to finish (core/tasks.py).
CMD ["uvicorn", "whitespace_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--timeout-graceful-shutdown", "25"]
