.PHONY: up down logs build reset test install lint

up:
	docker-compose up -d

down:
	docker-compose down

logs:
	docker-compose logs -f

build:
	docker-compose build --no-cache

reset:
	docker-compose run --rm memory_reset python scripts/weekly_reset.py

test:
	pytest tests/ -v

install:
	pip install -r requirements.txt -r requirements-dev.txt
	playwright install chromium

lint:
	ruff check agents/ tools/ schemas/ memory/ scripts/
	black --check agents/ tools/ schemas/ memory/ scripts/

format:
	black agents/ tools/ schemas/ memory/ scripts/
	ruff check --fix agents/ tools/ schemas/ memory/ scripts/
