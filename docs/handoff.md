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
- `Choose time`: ask for a new time in a normal text message and reschedule the same reminder.

If the user does not press any button, the worker auto-repeats after the configured interval. Default repeat interval is 5 minutes. After a successful timeout repeat, the worker tries to delete the previous fired reminder message so unread repeats do not flood the chat; if Telegram refuses deletion, it falls back to removing the old message keyboard.

## MVP Non-Goals

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

Use `reminders.intake` for input-source strategies. Text and voice input share the same parser and
reminder service path. Voice input transcribes Telegram voice/audio locally with `faster-whisper`,
then feeds the transcript into the shared intake flow.

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

## User Menu v1.0

The bot now has a secondary menu surface. `/start` and `/menu` install a persistent two-column
reply-keyboard panel near the Telegram text input, similar to Telegram bots that show a bottom menu
under the composer. It does not replace one-message reminder creation; users can still send text or
voice directly.

Menu screens:

- `⚙️ Settings`: shows and updates `user_settings.timezone` and `repeat_interval_minutes`.
- `🌍 Timezone`: preset-only selection for `Europe/Minsk`, `UTC`, `Europe/Warsaw`,
  `Europe/Moscow`, and `America/New_York`.
- `🔁 Repeat interval`: preset-only selection for `5`, `10`, `15`, `30`, `60`, and `120` minutes.
- `📌 Active reminders`: read-only list of up to 10 non-archived reminders in `active`,
  `snoozed`, or `sent`.
- `📋 Task history`: read-only list of up to 10 recent non-archived reminders across current and
  completed statuses.
- `🗄️ Archive`: read-only list of completed/read reminders from the last 90 days.
- `✍️ New reminder`: tells the user to send a reminder as text or voice.
- `ℹ️ Help`: short reminder workflow help.

Inline menu navigation uses `MenuCallback` and `MenuActionEnum` in
`src/nudge_bot/bot/callbacks.py`. These values are not persisted in `callback_events`; persisted
callback events remain for reminder and draft lifecycle actions only. Reply-keyboard menu buttons
send normal text, and `src/nudge_bot/bot/routers/menu.py` handles those labels before the reminders
text router can parse them as reminders.

## Current Session Handoff

This session implemented, reviewed, and lightly stabilized the text-based `Choose time` edit flow, then added local voice/audio reminder creation.

What changed:

- `Choose time` is no longer a placeholder. Pressing it sends a normal chat message asking for a new time, with a `Cancel` button.
- The edit state is durable: `ReminderEditTimeService` creates or reuses a pending `DraftTypeEnum.REMINDER_EDIT_TIME` draft.
- The next user text message is parsed through the existing `parse_reminder_text` path, but only `due_at` is applied. `reminder_text` stays unchanged.
- Successful edit-time application moves the same reminder to `snoozed` at the chosen UTC due time.
- Cancelling closes the edit-time draft and deletes only the prompt message, leaving the original fired reminder message intact.
- While a non-expired edit-time draft is pending, due claiming suppresses that reminder so auto-repeat does not fire over the user's custom-time flow.
- The edit-time draft payload contract is centralized in `src/nudge_bot/reminders/draft_payloads.py`.
- A partial unique index now enforces one pending edit-time draft per user: `alembic/versions/20260628_2045_add_pending_edit_time_draft_unique_index.py`.
- The migration defensively cancels older duplicate pending edit-time drafts before creating that unique index.
- `README.md`, `docs/database-schema.md`, and the living ExecPlan were updated to reflect the implemented flow.

Review fixes applied:

- Reminder rows are locked before edit-time application so stale or terminal reminders are not rewritten.
- Starting `Choose time` serializes by locking the user row before checking or creating the pending edit-time draft.
- Repeated taps on the same `Choose time` callback do not create duplicate drafts and do not spam duplicate prompt messages.
- Completed or archived reminders are handled gracefully and do not create edit-time drafts.
- The due-claim suppression uses the typed edit-time draft payload helper instead of open-coded JSON key strings.

Validation from this session:

- `pytest tests/reminders/services/test_edit_time_service.py`: 9 passed.
- `.venv\Scripts\python.exe -m pytest`: 80 passed.
- `ruff check .`: passed.
- `ruff format --check .`: passed.
- `uv run pytest`: blocked in this sandbox because `faster-whisper` requires a PyPI fetch and network access was denied.
- Test runs still show a pytest cache warning in this Codex Windows sandbox because `.pytest_cache` cannot be written; it does not indicate a test failure.

Lightweight stabilization added:

- `tests/reminders/services/test_edit_time_service.py::test_choose_time_replaces_pending_draft_for_other_reminder` now covers the case where a user starts `Choose time` for another reminder while an older edit-time draft is pending. The old draft is cancelled and the new draft owns the next text message.

Voice input added:

- Telegram `voice` and `audio` messages are accepted by the reminders router.
- Voice/audio is downloaded through aiogram, rejected before download when Telegram reports a file larger than `VOICE_MAX_FILE_SIZE_MB` or longer than `VOICE_MAX_DURATION_SECONDS`, then transcribed locally with `faster-whisper`.
- The default transcription configuration is `base` model, `int8` compute, `cpu` device, and `ru` language.
- Voice transcription is warmed at bot startup when possible and uses fast single-beam decoding, no timestamps, no previous-text conditioning, and VAD filtering.
- The bot immediately sends `Transcribing...` for accepted voice/audio messages, then edits that message with the final reminder result.
- Transcripts are routed through the shared reminder intake path. Confident parses create reminders directly; uncertain parses create confirmation drafts.
- Voice-created reminders and confirmed voice drafts use `ReminderSourceTypeEnum.VOICE`.
- Voice metadata is stored in JSON metadata/payload without raw audio or duplicate transcript text: language, duration, model, Telegram `file_unique_id`, and MIME type.
- Voice messages do not satisfy pending `Choose time` edit drafts; the bot asks the user to send the new time as text or press `Cancel`.
- Auto-repeat cleanup now uses the previous successful `reminder_attempts.telegram_message_id`: after sending a timeout repeat for a reminder that was already `sent`, the worker deletes the previous fired message, or removes its inline keyboard if deletion fails.
- Service result outcomes and parser intents now use `StrEnum` vocabulary instead of ad hoc `Literal` string outcomes.

Important implementation files touched:

- `src/nudge_bot/storage/repositories/reminders.py`
- `src/nudge_bot/storage/repositories/drafts.py`
- `src/nudge_bot/storage/repositories/users.py`
- `src/nudge_bot/reminders/services/edit_time.py`
- `src/nudge_bot/reminders/draft_payloads.py`
- `src/nudge_bot/bot/routers/reminders.py`
- `src/nudge_bot/bot/keyboards.py`
- `src/nudge_bot/reminders/services/intake.py`
- `src/nudge_bot/reminders/services/voice.py`
- `alembic/versions/20260628_2045_add_pending_edit_time_draft_unique_index.py`
- `tests/reminders/services/test_edit_time_service.py`
- `tests/bot/test_reminders.py`
- `tests/storage/test_reminder_repository.py`
- `tests/storage/test_draft_repository.py`
- `tests/reminders/services/test_voice_service.py`

## Next Implementation Step

Start from `.agent/execplans/tg-reminder-bot-mvp.md`.

Concrete next step: run a real local Telegram smoke test that opens `/menu`, changes timezone and
repeat interval presets, checks active/history/archive screens, then creates and completes a short
text reminder to verify the archive dashboard. Keep PostgreSQL race/multi-worker integration
coverage deferred unless the plan is explicitly reopened for hardening.

## Northflank CI/CD Handoff

Deployment documentation lives in `docs/deployment-northflank.md`. The repository has a GitHub
Actions workflow at `.github/workflows/ci-cd.yml` that runs Ruff, format check, tests, and a Docker
build. On the production branch it pushes `ghcr.io/<github-owner>/nudge-bot:latest` and calls
Northflank deployment hooks for the two runtime services.

Northflank should run one shared image as two deployment services:

- `nudge-bot`: custom command `nudge-bot`; set `RUN_MIGRATIONS=true`.
- `nudge-worker`: custom command `nudge-worker`; set `WAIT_FOR_MIGRATIONS=true`.

Both services need `BOT_TOKEN`, `DATABASE_URL`, timezone/repeat defaults, scheduler interval, and
voice settings. Northflank PostgreSQL may provide `DATABASE_URL` with `?sslmode=require`; the app and
Alembic path normalize that for `asyncpg`, so the query parameter can stay in the environment value.

GitHub repository secrets, not local `.env` values, must hold the Northflank deploy hook URLs:

- `NORTHFLANK_BOT_DEPLOY_HOOK_URL`
- `NORTHFLANK_WORKER_DEPLOY_HOOK_URL`

Observed Northflank deployment issues and resolutions:

- If bot logs show `TypeError: connect() got an unexpected keyword argument 'sslmode'`, ensure the
  Alembic `DATABASE_URL` normalization fix is deployed.
- If bot exits while downloading `faster-whisper-base` from Hugging Face without a Python traceback,
  the small Northflank instance is likely terminating the process during voice model load. Use a
  smaller model or disable voice warm-up for hosted testing so text reminders can start first.
- If logs show `duplicate key value violates unique constraint "users_telegram_user_id_uidx"`, that
  indicates a concurrent first-message race in `UserRepository.get_or_create`; the intended fix is a
  PostgreSQL upsert on `users.telegram_user_id` plus `ON CONFLICT DO NOTHING` for `user_settings`.
