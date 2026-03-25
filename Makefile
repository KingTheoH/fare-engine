# Fare Construction Engine — Makefile

.PHONY: up down db-migrate db-upgrade db-downgrade seed test lint format

# === Infrastructure ===

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

# === Database ===

db-migrate:
	# Usage: make db-migrate MSG="add carrier yq column"
	cd backend && alembic revision --autogenerate -m "$(MSG)"

db-upgrade:
	cd backend && alembic upgrade head

db-downgrade:
	cd backend && alembic downgrade -1

db-reset:
	docker compose down -v
	docker compose up -d postgres
	sleep 3
	cd backend && alembic upgrade head
	cd backend && python scripts/seed_carriers.py

seed:
	cd backend && python scripts/seed_carriers.py

# === Development ===

backend-dev:
	cd backend && uvicorn app.main:app --reload --port 8000

frontend-dev:
	cd frontend && npm run dev

worker-dev:
	cd backend && celery -A app.tasks.celery_app worker --loglevel=debug --concurrency=2

# === Testing ===

test:
	cd backend && pytest tests/ -v --ignore=tests/test_automation

test-all:
	cd backend && pytest tests/ -v

test-integration:
	cd backend && pytest tests/ -v -m integration

# === Code Quality ===

lint:
	cd backend && ruff check .
	cd backend && mypy app/

format:
	cd backend && ruff format .

# === Install ===

install-backend:
	cd backend && pip install -e ".[dev]"
	cd backend && playwright install chromium

install-frontend:
	cd frontend && npm install

install: install-backend install-frontend
