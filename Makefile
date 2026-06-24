.PHONY: help sync infra migrate downgrade bot worker run test lint format check pre-commit

help:
	@echo Available commands:
	@echo   make sync        Install dependencies with uv
	@echo   make infra       Start local infrastructure
	@echo   make migrate     Upgrade database to Alembic head
	@echo   make downgrade   Downgrade database by one Alembic revision
	@echo   make bot         Run Telegram bot in the current terminal
	@echo   make worker      Run scheduler worker in the current terminal
	@echo   make run         Run bot and worker in separate PowerShell windows
	@echo   make test        Run tests
	@echo   make lint        Run Ruff lint
	@echo   make format      Format code with Ruff
	@echo   make check       Run lint, format check, and tests

sync:
	uv sync

infra:
	docker compose up -d postgres

migrate:
	uv run alembic upgrade head

downgrade:
	uv run alembic downgrade -1

bot:
	uv run nudge-bot

worker:
	uv run nudge-worker

run:
	powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process powershell -ArgumentList '-NoExit','-Command','Set-Location ''$(CURDIR)''; uv run nudge-bot'; Start-Process powershell -ArgumentList '-NoExit','-Command','Set-Location ''$(CURDIR)''; uv run nudge-worker'"

test:
	uv run pytest

lint:
	uv run ruff check .

format:
	uv run ruff format .

check:
	uv run ruff check .
	uv run ruff format --check .
	uv run pytest

pre-commit:
	uv run pre-commit run --all-files
