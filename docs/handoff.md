# Project Handoff

This file is the short shared-memory entry point for continuing the Nudge Telegram bot project in another chat.

## Read These First

- `AGENTS.md`: project-wide rules, selected stack, and bot development practices.
- `README.md`: concise project overview and MVP scope.
- `.agent/execplans/tg-reminder-bot-mvp.md`: living ExecPlan for implementation.
- `docs/database-schema.md`: current database ER diagram, enum types, table meanings, and index strategy.
- `.omx/specs/deep-interview-tg-reminder-bot.md`: product requirements and UX flow.

## Product Summary

Nudge is a private-first Telegram reminder bot. The main pain is that Telegram scheduled messages are slow to create and clutter saved messages. The MVP should let the user send one plain text message to the bot, parse reminder text plus date/time, create a one-off reminder, and later send a notification with action buttons.

MVP buttons on a fired reminder:

- `Read`: mark the reminder completed/read, stop active repeats, keep history.
- `Repeat`: repeat after the user's configured short-repeat interval.
- `Choose time`: currently returns an MVP placeholder; the edit-time state machine is still deferred.

If the user does not press any button, future MVP work should auto-repeat after the configured interval. Default repeat interval is 5 minutes.

## MVP Non-Goals

- No voice creation in the first version.
- No recurring reminders in the first version.
- No full idea inbox in the first version.
- No payments or subscriptions.
- No advertising module yet.
- No Redis/Celery/APScheduler/FastAPI/MongoDB in the MVP unless the plan and `AGENTS.md` are updated.
- No webhook-only deployment path in the MVP; use long polling first.

## Selected Stack

- Python 3.12+
- aiogram 3.x
- PostgreSQL
- SQLAlchemy 2.x async ORM
- asyncpg
- Alembic
- pydantic-settings
- dateparser plus project-owned confidence rules
- custom DB-backed polling worker
- pytest and pytest-asyncio
- Ruff
- uv
- Docker Compose

If this stack changes, update `AGENTS.md`, `.agent/execplans/tg-reminder-bot-mvp.md`, and any affected docs in the same change.

## Architecture Summary

Use one Python codebase with two local runtime entrypoints. Docker Compose is for local
infrastructure such as PostgreSQL; the Python application should normally run directly on the
developer's computer through `uv`.

- `bot`: aiogram long polling process started with `uv run nudge-bot`; it receives Telegram messages and callback queries.
- `worker`: DB-backed polling worker started with `uv run nudge-worker`; it scans PostgreSQL for due reminders and sends notifications.

Internal flow:

    Telegram adapter -> parser/intake -> reminder service -> storage -> worker -> Telegram delivery

Keep Telegram handlers thin. Business rules should live in services/domain modules and be testable without Telegram.

Use `reminders.intake` for input-source strategies. Text input is the first strategy. Future voice
input should be a second strategy that transcribes audio and then reuses the same parser and reminder
service path.

Use repository classes through `storage.unit_of_work.UnitOfWork` instead of passing raw
`AsyncSession` into application services. The top-level bot update or worker job should own the Unit
of Work lifetime.

## Database Summary

The current schema direction is in `docs/database-schema.md`.

Core tables:

- `users`
- `user_settings`
- `reminders`
- `reminder_attempts`
- `drafts`
- `callback_events`

Important decisions:

- Use PostgreSQL enum types for bounded values.
- Keep enum classes in domain-facing modules and map them explicitly to PostgreSQL enum type names in ORM models.
- Store final reminders in `reminders`, not generic `items`.
- Use `reminders.type`, currently only `one_off`.
- Store final reminder text in `reminders.reminder_text`.
- Do not store `raw_text`, `normalized_text`, or final `confidence` on `reminders`.
- Store temporary parse confidence only in `drafts.parse_confidence`.
- Use `archived_at`; do not use `deleted_at`.
- Use `drafts`, not `interaction_drafts`.
- `users` should not store `first_name` or `last_name`.

Important indexes are documented in `docs/database-schema.md`, including due-reminder scanning, callback idempotency, pending drafts, history, delivery retries, and rate-limit support.

## Timezone Decision

Store all database timestamps in UTC. Store each user's timezone in `user_settings.timezone`.

Telegram Bot API does not reliably provide a user's timezone. For MVP, use a default such as `Europe/Minsk` and expose a settings flow to change it. Timezone is needed to parse phrases such as "tomorrow at 9" and display reminders in the user's local time.

## Telegram Update Strategy

Use long polling for MVP. It works locally without a public HTTPS URL.

Webhooks are reserved for later production deployment. A webhook means Telegram sends updates to a public HTTPS endpoint. It can reduce infrastructure polling and fit production HTTP deployments, but requires a domain, TLS, endpoint protection, and deployment setup.

## Callback Strategy

Use aiogram CallbackData factories for inline button payloads instead of hand-built strings.

Button actions must be idempotent. Repeated presses of `Read` or `Repeat` should not corrupt state or create duplicate repeats. Fired-reminder callbacks use a stable key shaped around reminder id, notification attempt id, and action.

Use `callback_events.callback_key` as a unique logical action key. This supports idempotency and future per-user button rate limiting.

## Next Implementation Step

Start from `.agent/execplans/tg-reminder-bot-mvp.md`.

Next implementation milestone:

1. Add automatic repeat when a delivered reminder remains `sent` with no user action.
2. Implement the `Choose time` edit flow.
3. Add integration coverage around PostgreSQL worker claiming and callback idempotency.
