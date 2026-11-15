# Whitespace

Tells an exporter where to sell a product next, and why now, using free global trade data, a data pipeline and an AI analyst.

## Repository layout

```
whitespace/
├── frontend/   Next.js app (UI, public market pages)
├── backend/    FastAPI service (API, AI agent)
├── pipeline/   data pipeline (download → clean → score → load)
├── shared/     schemas shared by pipeline and backend
├── docs/adr/   architecture decisions
├── data/       local pipeline output (gitignored)
├── compose.yaml
└── Makefile    every common command: run `make`
```

## Prerequisites

- Docker with Compose
- [uv](https://docs.astral.sh/uv/) (Python 3.12 is installed automatically)
- Node.js 20.9+ with pnpm (`corepack enable`)

## Quick start

```bash
make env       # create .env from .env.example, then add your keys
make up        # build and start everything in Docker
```

| Service  | URL |
|----------|-----|
| Web      | http://localhost:3400 |
| API docs | http://localhost:8400/docs |
| Postgres | localhost:5440 (user/password/db: `whitespace`) |

Ports are set in `.env` and avoid 3000, 8000, 5434, 5678 and 6380, which the sumhuman project uses.

## Local development (hot reload)

```bash
make install   # Python + frontend dependencies
make db        # Postgres only, in Docker
make migrate   # apply migrations
make api       # API on :8400
make web       # frontend on :3400 (second terminal)
```

## Quality checks

```bash
make check     # lint + typecheck + tests (what CI runs)
make format    # auto-format Python
make gen-client  # regenerate frontend API types after changing an endpoint
```

## Keys

Only `GOOGLE_API_KEY` (Google AI Studio, free) is needed for v0's AI features. `GROQ_API_KEY` is an optional fallback. See `.env.example` for everything else.
