.PHONY: up down build test lint fmt clean db-revision db-upgrade

up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build

logs:
	docker compose logs -f

test:
	docker compose run --rm app pytest

lint:
	docker compose run --rm app ruff check .

fmt:
	docker compose run --rm app ruff check --fix .
	docker compose run --rm app black .

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

db-revision:
	docker compose run --rm app alembic revision --autogenerate -m "$(msg)"

db-upgrade:
	docker compose run --rm app alembic upgrade head
