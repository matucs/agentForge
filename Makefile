.PHONY: up down backend-test backend-lint backend-typecheck frontend-build frontend-typecheck test demo demo-failure eval

up:
	docker compose up -d --build
	docker compose exec backend alembic upgrade head

down:
	docker compose down

backend-lint:
	cd backend && . .venv/bin/activate && ruff check app

backend-typecheck:
	cd backend && . .venv/bin/activate && mypy app

backend-test:
	cd backend && . .venv/bin/activate && pytest -q

frontend-typecheck:
	cd frontend && npx tsc --noEmit

frontend-build:
	cd frontend && npm run build

test: backend-lint backend-typecheck backend-test frontend-typecheck frontend-build

demo:
	cd backend && . .venv/bin/activate && python -m app.demos.full_demo

demo-failure:
	cd backend && . .venv/bin/activate && python -m app.demos.failure_scenarios

eval:
	cd backend && . .venv/bin/activate && python -m app.evaluation.runner
