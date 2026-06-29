.PHONY: help install db backend frontend test demo up down

help:
	@echo "Targets:"
	@echo "  install   Install backend (venv) + frontend deps"
	@echo "  db        Start only Postgres (docker compose)"
	@echo "  backend   Run the FastAPI backend (reload)"
	@echo "  frontend  Run the Next.js dashboard"
	@echo "  test      Run backend tests"
	@echo "  demo      Run one pipeline from the terminal (needs GEMINI_API_KEY + db)"
	@echo "  up/down   Full stack via docker compose"

install:
	cd backend && python3 -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"
	cd frontend && npm install

db:
	docker compose up -d db

backend:
	cd backend && . .venv/bin/activate && uvicorn app.main:app --reload --port 8000

frontend:
	cd frontend && npm run dev

test:
	cd backend && . .venv/bin/activate && pytest -q

migrate:
	cd backend && . .venv/bin/activate && alembic upgrade head

demo:
	cd backend && . .venv/bin/activate && python -m app.cli "$(TITLE)" "$(BODY)"

up:
	docker compose up --build

down:
	docker compose down
