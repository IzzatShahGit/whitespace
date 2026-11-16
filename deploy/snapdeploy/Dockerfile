# syntax=docker/dockerfile:1
# One ARM64 image with the web app and the API, for SnapDeploy's free tier.
# Build with:  make snapdeploy   (scripts/snapdeploy-build.sh)
#
# Why one container: SnapDeploy only wakes a sleeping app for real browsers and limits
# each IP to 100 requests/minute, so the browser must reach the app directly (not via a
# proxy such as Vercel). Next.js serves the site on $PORT and forwards /api/* to the API
# on 127.0.0.1:18000 inside the container, exactly like docker compose does locally.
#
# The local stack (compose.yaml, backend/Dockerfile, frontend/Dockerfile) is unaffected.

# Internal API address, baked into the web app's routing table at build time.
ARG API_INTERNAL_URL=http://127.0.0.1:18000

# ---------- web: build on the host CPU (fast; the output is plain JavaScript) ----------
FROM --platform=$BUILDPLATFORM node:22-alpine AS web-build
ARG API_INTERNAL_URL
ENV PNPM_HOME=/pnpm PATH=/pnpm:$PATH NEXT_TELEMETRY_DISABLED=1
RUN corepack enable
WORKDIR /app
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN --mount=type=cache,id=pnpm,target=/pnpm/store pnpm install --frozen-lockfile
COPY frontend/ .
ENV API_INTERNAL_URL=$API_INTERNAL_URL
RUN pnpm build
# sharp (image optimisation for next/image) is the only native module Next traces in, and
# it is built for the host CPU. The app doesn't use next/image, so drop it, then refuse to
# continue if any other CPU-specific binary slipped into the bundle.
RUN rm -rf .next/standalone/node_modules/.pnpm/@img+* .next/standalone/node_modules/@img \
 && if find .next/standalone -name '*.node' | grep -q .; then \
      echo "Native module found in the web bundle:"; find .next/standalone -name '*.node'; exit 1; \
    fi

# ---------- api: same steps as backend/Dockerfile, for the target CPU ----------
FROM ghcr.io/astral-sh/uv:0.9-python3.12-bookworm-slim AS api-build
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY backend/pyproject.toml backend/
COPY pipeline/pyproject.toml pipeline/
COPY shared/pyproject.toml shared/
RUN --mount=type=cache,target=/root/.cache/uv,id=uv-arm64 \
    uv sync --frozen --no-dev --package whitespace-api --no-install-workspace
COPY shared shared
COPY backend backend
RUN --mount=type=cache,target=/root/.cache/uv,id=uv-arm64 \
    uv sync --frozen --no-dev --package whitespace-api --no-editable

# ---------- node runtime (glibc build, matches the Debian base below) ----------
FROM node:22-bookworm-slim AS node-bin

# ---------- runtime ----------
FROM python:3.12-slim-bookworm AS runtime
RUN useradd --create-home --uid 1000 app
WORKDIR /app
COPY --from=node-bin /usr/local/bin/node /usr/local/bin/node
COPY --from=api-build --chown=app:app /app/.venv /app/.venv
COPY --chown=app:app backend/alembic.ini ./backend/alembic.ini
COPY --chown=app:app backend/migrations ./backend/migrations
COPY --from=web-build --chown=app:app /app/.next/standalone ./web
COPY --from=web-build --chown=app:app /app/.next/static ./web/.next/static
COPY --from=web-build --chown=app:app /app/public ./web/public
COPY --chown=app:app --chmod=755 deploy/snapdeploy/start.sh ./start.sh
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 \
    NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 \
    NODE_OPTIONS=--max-old-space-size=192 \
    PORT=8000
USER app
EXPOSE 8000
CMD ["/app/start.sh"]
