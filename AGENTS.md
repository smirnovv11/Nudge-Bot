# ExecPlans

When writing complex features or significant refactors, use an ExecPlan (as described in .agent/PLANS.md) from design to implementation.

# Project Stack

The selected MVP stack for this repository is:

- Runtime: Python 3.12+
- Telegram framework: aiogram 3.x
- Database: PostgreSQL
- Database access: SQLAlchemy 2.x async ORM with asyncpg
- Migrations: Alembic
- Configuration: pydantic-settings with `.env`
- Human date parsing: dateparser plus a project-owned confidence layer
- Scheduling: custom DB-backed polling worker
- Tests: pytest and pytest-asyncio
- Quality tools: Ruff for linting and formatting
- Packaging and commands: uv
- Local infrastructure: Docker Compose

Do not add Redis, Celery, APScheduler, FastAPI, MongoDB, or a webhook-only deployment path to the MVP unless the project plan is explicitly updated. Redis is reserved for future queueing, distributed locks, rate limiting, or multi-worker scale. Webhooks are reserved for a later production deployment; the MVP should use long polling.

If this stack changes, update this `AGENTS.md` file in the same change as the architecture or implementation plan.

# Bot Development Practices

Keep Telegram handlers thin. aiogram handlers should receive messages and callback queries, call application services, and render replies; reminder state, scheduling, parsing, and storage rules belong in domain and service modules.

Store durable reminder state in PostgreSQL. Active reminders, due times, completion status, attempts, user settings, and confirmation drafts must survive process restarts.

Use UTC timestamps in the database and store each user's timezone separately. Convert to local time only at input/output boundaries.

Make reminder actions idempotent. Pressing `Read`, `Repeat`, or `Choose time` more than once must not create duplicate repeats, duplicate completions, or inconsistent state.

Use aiogram CallbackData factories for inline button payloads instead of hand-built callback strings.

Treat Telegram delivery retry and user reminder repeat as separate concepts. A failed Telegram API send should be retried as delivery. A delivered notification with no user action should create the next reminder fire time.

Avoid logging full reminder text unless explicitly needed for local debugging. Prefer ids, statuses, timestamps, and short structured events.

Separate logical blocks of code with a blank line for readability.
