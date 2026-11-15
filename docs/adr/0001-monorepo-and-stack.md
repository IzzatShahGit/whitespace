# 0001: One repository, and the v0 stack

Date: 2026-11-15. Status: accepted.

## Decision

- **One repository** with `frontend/`, `backend/`, `pipeline/` and `shared/`. Each deploys on its own; CI runs only the parts that changed.
- **Frontend:** Next.js (App Router), TypeScript, Tailwind. The API client is typed from the backend's OpenAPI spec.
- **Backend:** FastAPI, SQLAlchemy 2 (async), Alembic, Postgres with pgvector and pg_trgm.
- **Pipeline:** Polars and DuckDB over Parquet; Spark, dbt and Airflow come later, when they solve a real problem.
- **Shared:** gold-table schemas that both the pipeline and the API import.
- **LLM:** LangChain chat models chosen by `LLM_PROVIDER` (Gemini by default, Groq as fallback, Ollama locally).
- **Everything runs in Docker**, configured only by environment variables.

## Why

The project must run at zero cost, so hosting follows whichever free tier fits. The current plan is Cloudflare Workers for the frontend, Azure Container Apps for the API, Neon for Postgres and Hugging Face Datasets for published data. Keeping every part a plain container with env-var configuration means moving a part changes configuration, not code.

## Local ports

Host ports 3000, 8000, 5434, 5678 and 6380 belong to the sumhuman project (5434 is its Postgres, even while stopped). Whitespace uses web 3400, API 8400, Postgres 5440 and Ollama 11444, all set in `.env`.
