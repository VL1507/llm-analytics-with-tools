.PHONY: format lint all build-sandbox up down

format:
	uv run ruff format
	uv run ruff check --fix

lint:
	uv run ruff check
	uv run pyrefly check
	uv run ty check 
	uv run mypy .

all: format lint

build-sandbox:
	docker build -t sandbox-image ./sandbox

up: build-sandbox
	docker compose up --build -d

down:
	docker compose down