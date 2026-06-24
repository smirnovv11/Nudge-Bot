# Nudge

Nudge is a private-first Telegram reminder bot. The MVP goal is speed: a user writes one plain text message such as "walk the dog in 20 minutes", the bot parses the reminder text and date/time, creates a one-off reminder, and later sends a notification with action buttons.

The product requirements live in `.omx/specs/deep-interview-tg-reminder-bot.md`. The implementation plan lives in `.agent/execplans/tg-reminder-bot-mvp.md`.

The shared database schema direction lives in `docs/database-schema.md`.

For continuing this work in another chat, start from `docs/handoff.md`.

## MVP Scope

The first version focuses on text-based one-off reminders. Voice creation, recurring reminders, a full idea inbox, payments, ads, and a web admin panel are intentionally deferred.

The main user flow is:

1. User sends plain text to the bot.
2. Bot parses reminder text and date/time.
3. If parsing is confident, bot creates the reminder immediately.
4. If parsing is uncertain, bot asks for a compact confirmation.
5. When due time arrives, bot sends the reminder with `Read`, `Repeat`, and `Choose time` actions.
6. If the user does nothing, the reminder repeats after the configured interval.

## Selected Stack

- Python 3.12+
- aiogram 3.x
- PostgreSQL
- SQLAlchemy 2.x async ORM
- asyncpg
- Alembic
- pydantic-settings
- dateparser plus project confidence rules
- custom DB-backed polling worker
- pytest and pytest-asyncio
- Ruff
- uv
- Docker Compose

Redis, Celery, APScheduler, FastAPI, MongoDB, and Telegram webhooks are not part of the MVP stack. They can be introduced later only when the plan and `AGENTS.md` are updated.

## Local Development

The recommended development setup runs only infrastructure in Docker and runs the Python
application directly on the computer.

Create a local environment file:

    copy .env.example .env

Put the Telegram bot token from BotFather into `.env`:

    BOT_TOKEN=123456:your-real-token-from-botfather

Start PostgreSQL:

    docker compose up -d postgres

Install dependencies and apply migrations:

    uv sync
    uv run alembic upgrade head

The same commands are available through `make`:

    make sync
    make infra
    make migrate
    make downgrade

The Makefile commands require GNU Make to be installed and available in `PATH`. If `make` is not
installed on Windows, run the `uv` and `docker compose` commands above directly.

Run the bot process in one terminal:

    uv run nudge-bot

Run the worker process in another terminal:

    uv run nudge-worker

Or use Makefile shortcuts:

    make bot
    make worker

To open bot and worker in separate PowerShell windows:

    make run

The `bot` process receives Telegram updates through long polling. It is the part that talks to
the user: `/start`, text messages, and inline button clicks.

The `worker` process is the scheduler. It periodically checks PostgreSQL for due reminders and
sends reminder notifications. Keeping it separate makes reminder delivery independent from
Telegram message intake and lets both loops stay simple.

For code checks, run:

    uv run pytest
    uv run ruff check .
    uv run ruff format --check .

Or:

    make check

To enable the git hook workflow:

    $env:PRE_COMMIT_HOME = "$PWD\\.pre-commit-cache"
    uv run pre-commit install
    uv run pre-commit run --all-files

## Architecture Direction

The application uses one Python codebase with two runtime entrypoints:

- `bot`: receives Telegram updates through long polling and handles user interaction.
- `worker`: polls PostgreSQL for due reminders and sends notifications.

The internal flow should be:

    Telegram adapter -> intake/parser -> reminder service -> storage -> scheduler worker -> Telegram delivery

Telegram-specific code should stay near the adapter layer. Reminder behavior should be testable without calling Telegram.

Reminder input handling is split from reminder parsing. Text input currently uses a small strategy
object that calls the parser directly. Future voice input should become a separate strategy that
transcribes audio first, then feeds the transcript into the same reminder parser and service flow.

Storage access is grouped behind repository classes and a Unit of Work. A Unit of Work owns one
database session and exposes repositories such as `users` and `reminders` for one bot update or one
worker job. This keeps transaction boundaries explicit while avoiding raw SQLAlchemy sessions in
application services.

## Development Practices

Use PostgreSQL as the source of truth for all durable reminder state. Do not rely on in-memory timers for active reminders.

Store all timestamps in UTC and keep a timezone setting per user.

Make callback actions idempotent so repeated button presses are safe.

Use aiogram CallbackData factories for structured inline button payloads.

Keep Telegram API delivery retries separate from user-facing reminder repeats.

Avoid logging full reminder text by default.
