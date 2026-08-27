.PHONY: up down build logs test-backend test-frontend

up:
	docker compose up

down:
	docker compose down

build:
	docker compose build

logs:
	docker compose logs -f

test-backend:
	cd backend && .venv/bin/pytest

test-frontend:
	cd frontend && npm run test:run
