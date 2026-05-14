.PHONY: format lint all

format:
	uv run ruff format
	uv run ruff check --fix

lint:
	uv run ruff check
	uv run pyrefly check
	uv run ty check 
	uv run mypy .

all: format lint