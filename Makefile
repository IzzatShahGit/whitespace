.DEFAULT_GOAL := help
FRONTEND := cd frontend &&

# Read ports from .env when it exists. Only these are exported to commands:
# secrets in .env stay out of every process environment (apps read .env themselves).
-include .env
export WEB_PORT API_PORT DB_PORT OLLAMA_PORT OLLAMA_MODEL

help: ## Show available commands
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

# ---------- setup ----------
install: ## Install Python and frontend dependencies
	uv sync
	$(FRONTEND) pnpm install

env: ## Create .env from .env.example (won't overwrite)
	@test -f .env && echo ".env already exists" || (cp .env.example .env && echo "created .env")

# ---------- run ----------
up: ## Start the whole stack in Docker (web :3400, api :8400, db :5440)
	docker compose up --build -d
	@echo "web http://localhost:$${WEB_PORT:-3400}  api http://localhost:$${API_PORT:-8400}/docs"

down: ## Stop the stack
	docker compose down

logs: ## Follow logs
	docker compose logs -f

ollama: ## Start local Ollama (dev only, capped at 2 CPUs / 6 GB) and pull the small model
	docker compose --profile ollama up -d ollama
	docker exec whitespace_ollama ollama pull $${OLLAMA_MODEL:-qwen2.5:3b}
	@echo "Set LLM_PROVIDER=ollama in .env to use it. Stop with: make ollama-stop"

ollama-stop: ## Stop Ollama and free its CPU/RAM (downloaded models stay on disk)
	docker compose --profile ollama stop ollama

ollama-clean: ## Remove Ollama and its downloaded models (frees disk)
	docker compose --profile ollama rm -sf ollama
	docker volume rm whitespace_ollama-data

db: ## Start only Postgres (for running api/web locally)
	docker compose up -d db

migrate: ## Apply database migrations (local Python)
	cd backend && uv run alembic upgrade head

api: ## Run the API with hot reload on :8400
	cd backend && uv run uvicorn whitespace_api.main:app --reload --port $${API_PORT:-8400}

web: ## Run the frontend with hot reload on :3400
	$(FRONTEND) pnpm dev

# ---------- quality ----------
lint: ## Lint and format-check everything
	uv run ruff check .
	uv run ruff format --check .
	$(FRONTEND) pnpm lint

format: ## Auto-format Python code
	uv run ruff format .
	uv run ruff check --fix .

typecheck: ## Type-check Python and TypeScript
	uv run mypy
	$(FRONTEND) pnpm typecheck

test: ## Run Python tests
	uv run pytest

check: lint typecheck test ## Everything CI runs

# ---------- codegen ----------
gen-client: ## Regenerate frontend API types from the backend
	uv run python -c "import json; from whitespace_api.main import app; print(json.dumps(app.openapi(), indent=2))" > frontend/openapi.json
	$(FRONTEND) pnpm gen:api

.PHONY: help install env up down logs ollama ollama-stop ollama-clean db migrate api web lint format typecheck test check gen-client
