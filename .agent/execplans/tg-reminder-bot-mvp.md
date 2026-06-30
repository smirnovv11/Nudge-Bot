# Build the Telegram Reminder Bot MVP

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This repository contains `.agent/PLANS.md`; this document must be maintained in accordance with that file. The implementation should also preserve the stack and bot practices recorded in `AGENTS.md`.

## Purpose / Big Picture

The user wants a faster replacement for Telegram scheduled messages. After this MVP, the user can open a Telegram bot, send one plain text message such as "walk the dog in 20 minutes", and receive a reminder at the right time without using Telegram's slow scheduled-message UI.

The first demonstrable behavior is a private Telegram bot that accepts text reminders, stores them durably in PostgreSQL, sends due notifications, and lets the user mark them as read/completed, repeat them after a configured interval, or choose a new time. The MVP uses long polling for Telegram updates and a database-backed polling worker for due reminders.

## Progress

- [x] (2026-06-24 00:00Z) Product direction clarified: speed-first text reminders, no voice, no recurring reminders, no full inbox in MVP.
- [x] (2026-06-24 00:00Z) MVP stack selected and documented in `AGENTS.md` and `README.md`.
- [x] (2026-06-24 00:00Z) Initial ExecPlan created.
- [x] (2026-06-24 00:00Z) Database diagram refined to use `reminders`, `drafts`, PostgreSQL enums, `archived_at`, and final reminder text without raw/normalized duplicates.
- [x] (2026-06-24 00:00Z) Database index strategy documented in `docs/database-schema.md`.
- [x] (2026-06-24 17:51Z) Scaffolded the Python project with `pyproject.toml`, `src/nudge_bot`, initial tests, Ruff configuration, and uv-compatible commands.
- [x] (2026-06-24 17:51Z) Added Docker Compose infrastructure and local `bot`/`worker` uv commands.
- [x] (2026-06-24 18:20Z) Revised the development workflow so Docker Compose runs only PostgreSQL and the Python app runs locally on the developer machine.
- [x] (2026-06-24 17:51Z) Implemented configuration loading with pydantic-settings and `.env.example`.
- [x] (2026-06-24 17:51Z) Implemented SQLAlchemy model declarations and the first Alembic migration matching the documented database tables and indexes.
- [x] (2026-06-24 18:28Z) Moved bounded state/action enums into domain-facing modules, configured ORM enum columns with explicit PostgreSQL type names and lowercase values, and added tests for the mapping.
- [x] (2026-06-24 18:28Z) Replaced free functions in storage with repository classes and introduced a Unit of Work boundary for application services.
- [x] (2026-06-24 18:28Z) Added a lightweight text input strategy so future voice input can transcribe first and then reuse the same parser/service path.
- [x] (2026-06-24 18:29Z) Mirrored the documented non-column indexes in SQLAlchemy model metadata and kept them in the baseline Alembic migration.
- [x] (2026-06-26 00:00Z) Implemented the first project-owned parser rule layer for Russian reminder phrases, confidence rules, explicit note markers, and conflict handling.
- [x] (2026-06-26 00:00Z) Implemented MVP draft-flow and aiogram text/draft handlers: confident parses create active reminders, uncertain parses create confirmation drafts, and draft callbacks support confirm/cancel.
- [x] (2026-06-26 00:00Z) Hardened draft confirmation after review: draft confirm/cancel now lock draft rows, enforce `expires_at`, avoid Telegram API calls inside open Unit of Work contexts, and tolerate invalid stored timezones by falling back safely.
- [x] (2026-06-26 00:00Z) Refactored reminder application services into class-based service modules, moved service result schemas into a dedicated module, kept a compatibility facade for existing imports, and reorganized tests by bot, config, storage, parser, and service layer.
- [x] (2026-06-26 00:00Z) Implemented the first DB-backed worker delivery loop: due reminders are claimed, sent through Telegram with fired-reminder buttons, delivery attempts are recorded, success marks reminders `sent`, and send failures return reminders to `active` for a later tick.
- [x] (2026-06-26 00:00Z) Added fired-reminder callback handling for `Read`, `Repeat`, and MVP-placeholder `Choose time`; `Read` completes reminders, `Repeat` snoozes by the user's repeat interval, and stable callback keys prevent one notification button event from applying twice.
- [x] (2026-06-28 19:30Z) Implemented auto-repeat for delivered reminders that remain `sent` with no user action: successful delivery now schedules the next unattended fire time from the user's repeat interval, and due scans include `sent` reminders.
- [x] (2026-06-28 20:15Z) Implemented the `Choose time` edit flow: the fired-reminder button creates or reuses a durable `reminder_edit_time` draft, the next text message is parsed for a replacement due time, and successful edits reschedule the existing reminder without changing its text.
- [x] (2026-06-28 20:45Z) Applied review fixes for the `Choose time` edit flow: due claiming suppresses reminders with a non-expired pending edit-time draft, edit-time application locks the reminder row before state checks, repeated `Choose time` taps no longer send duplicate prompt messages, and a partial unique index prevents duplicate pending edit-time drafts per user.
- [x] (2026-06-28 21:05Z) Applied follow-up review hardening: `Choose time` creation now serializes by locking the user row before checking pending drafts, edit-time draft payload keys are centralized in a typed helper, the unique-index migration cancels older duplicate pending edit-time drafts before creating the index, and `README.md` no longer describes `Choose time` as a placeholder.
- [x] (2026-06-28 21:20Z) Completed a lightweight `Choose time` test-stabilization pass by adding unit coverage for replacing a pending edit-time draft that points at a different reminder, without expanding into PostgreSQL race or multi-worker integration coverage.
- [ ] Add tests for parsing, reminder state transitions, idempotent button handling, and worker claiming. Current state: parser, draft-flow service, confirmation keyboard, confirm/cancel idempotency, worker tick, delivery success/failure, fired-reminder callback idempotency, auto-repeat, and `Choose time` edit-flow tests exist; PostgreSQL-backed integration coverage is deliberately deferred until after the next product slice is planned.
- [x] (2026-06-28 21:20Z) Ran local validation with bundled Python and repository-local uv cache: pytest passed with 71 tests, Ruff lint passed, and Ruff format check passed.
- [x] (2026-06-28 22:05Z) Implemented voice/audio reminder creation as the next input strategy: Telegram voice/audio is transcribed locally with `faster-whisper`, routed through the shared parser/intake flow, and stored as `source_type = voice` with minimal transcript metadata.
- [x] (2026-06-28 22:15Z) Ran post-voice validation through the existing `.venv`: pytest passed with 80 tests, Ruff lint passed, and Ruff format check passed. `uv run pytest` is blocked until `uv.lock` can be updated with network access for `faster-whisper`.
- [x] (2026-06-30 00:00Z) Optimized the local Whisper voice path for MVP responsiveness: default model changed from `small` to `base`, voice duration is capped at 15 seconds, transcription warms at bot startup, fast single-beam/VAD options are used, and accepted voice messages immediately show `Transcribing...`.

## Surprises & Discoveries

- Observation: The repository started as a planning shell with no app code.
  Evidence: The root contains `AGENTS.md`, `.agent/PLANS.md`, and `.omx` planning artifacts, but no Python package yet.

- Observation: In full reminder sentences, `dateparser.parse()` did not extract the due time from text such as "walk the dog in 20 minutes"; `dateparser.search.search_dates()` is needed for the initial parser scaffold.
  Evidence: `uv run pytest` first failed `tests/test_parser.py::test_parse_relative_reminder_confident` because the draft intent was `unknown`; after switching to `search_dates`, the same test passed.

- Observation: In this Windows Codex App environment, `uv` and system Python were not initially on PATH. The bundled Codex Python could run the project after installing `uv`, and `UV_CACHE_DIR` had to point inside the repository because the default user cache path was sandbox-blocked.
  Evidence: `uv run pytest` first failed with "uv is not recognized"; `python --version` was not found; `UV_CACHE_DIR=C:\Users\sqd12\Documents\Nudge\.uv-cache` allowed `python -m uv run pytest` to resolve and run the tests.

- Observation: SQLAlchemy ORM enum columns need explicit PostgreSQL enum type names and value mapping to match the handcrafted Alembic migration.
  Evidence: The first migration creates lowercase PostgreSQL enum values such as `active` and `one_off`; `tests/test_models.py` now asserts that ORM enum columns use the matching type names and enum values.

- Observation: The first schema migration already contains the documented indexes, so an extra corrective migration is unnecessary while local development is still on the first revision.
  Evidence: `20260624_1751_create_reminder_tables.py` creates the documented reminder, draft, callback, attempt, and user indexes; `storage.models` now also declares the non-column indexes in ORM metadata.

- Observation: The bot-facing draft-flow needs a deliberate split between local parsing time and UTC persistence.
  Evidence: `handle_text_reminder` parses with the user's timezone, stores `reminders.due_at` and `drafts.parsed_due_at` as UTC timestamps, and keeps the draft timezone in payload for user-facing callback formatting.

- Observation: Sequential idempotency tests are not enough for Telegram callback safety.
  Evidence: Review found that a plain draft `SELECT` allowed two concurrent confirm callbacks to see `pending` and create duplicate reminders; `DraftRepository.get_by_id_for_user_for_update` now locks the row inside the Unit of Work before confirm/cancel status decisions.

- Observation: Auto-repeat can reuse the existing `reminders.due_at` field instead of adding an auto-repeat timestamp.
  Evidence: The worker already orders deliverable reminders by `due_at`, and `ReminderDeliveryService.mark_sent` now moves `due_at` to `sent_at + user_settings.repeat_interval_minutes` while keeping the reminder in `sent`.

- Observation: `Choose time` can reuse the existing parser without changing the parser contract.
  Evidence: `ReminderEditTimeService.apply_edit_time_text` calls `parse_reminder_text` and uses only `parsed.due_at`; the reminder text remains unchanged, so inputs like "через 20 минут" can reschedule an existing reminder even when there is no new reminder text.

- Observation: Starting `Choose time` should not consume or replace the original fired-reminder controls.
  Evidence: The callback now sends a separate prompt message with a `Cancel` button, while the original fired reminder message keeps its `Read`, `Repeat`, and `Choose time` buttons for the normal reminder flow.

- Observation: A pending edit-time draft must be visible to the scheduler.
  Evidence: The due-reminder repository now excludes reminders that have a non-expired pending `reminder_edit_time` draft for the same reminder id, so auto-repeat does not fire while the bot is waiting for a custom time.

- Observation: A user can only have one pending edit-time session, so choosing time for a different reminder should retire the older pending draft before creating the new one.
  Evidence: `ReminderEditTimeService._handle_existing_pending_draft` cancels the old draft when its payload points at another reminder, and `tests/reminders/services/test_edit_time_service.py::test_choose_time_replaces_pending_draft_for_other_reminder` now locks in that lifecycle behavior.

- Observation: Voice input fits the existing intake boundary when source metadata is made explicit.
  Evidence: `ReminderIntakeService.handle_reminder_text` accepts `source_type` and `source_metadata`; `VoiceReminderService` transcribes audio and delegates the transcript to that shared path, while `DraftFlowService.confirm_draft` preserves voice source metadata from draft payloads.

- Observation: Local CPU transcription must optimize perceived latency, not only raw model time.
  Evidence: Voice handling now sends `Transcribing...` before download/transcription, warms the `faster-whisper` model at bot startup, rejects voice messages longer than `VOICE_MAX_DURATION_SECONDS`, and calls `model.transcribe` with `beam_size=1`, `best_of=1`, `without_timestamps=True`, `condition_on_previous_text=False`, and `vad_filter=True`.

## Decision Log

- Decision: Use Python 3.12+ and aiogram 3.x for the Telegram bot.
  Rationale: Python is a good fit for bot development and future speech-to-text work. aiogram is async-first and supports routers, callback queries, long polling, webhooks, middleware, and typed callback data.
  Date/Author: 2026-06-24 / Codex

- Decision: Use PostgreSQL instead of MongoDB for the MVP.
  Rationale: Reminder delivery depends on indexed due-time queries, statuses, transactions, and safe worker claiming. PostgreSQL also allows flexible metadata through JSONB if future inbox or voice features need it.
  Date/Author: 2026-06-24 / Codex

- Decision: Do not include Redis in the MVP.
  Rationale: A single DB-backed polling worker can satisfy the private-first MVP. Redis can be introduced later for queues, distributed locks, rate limiting, or multi-worker scale when the need is real.
  Date/Author: 2026-06-24 / Codex

- Decision: Use long polling for MVP and reserve webhooks for production deployment.
  Rationale: Long polling avoids public HTTPS infrastructure and is easier to run locally. Webhooks become useful when the bot has a stable public deployment endpoint and needs faster push-style update delivery.
  Date/Author: 2026-06-24 / Codex

- Decision: Use aiogram CallbackData factories for inline buttons.
  Rationale: CallbackData gives typed, parseable callback payloads and avoids fragile hand-built strings.
  Date/Author: 2026-06-24 / Codex

- Decision: Rename the central persistence table from `items` to `reminders` and remove `kind`, `deleted_at`, final `confidence`, `raw_text`, and `normalized_text` from final reminders.
  Rationale: The MVP stores reminders, not generic items. Future notes should not make the MVP schema vague. Final reminders only need accepted reminder text and due time; parse confidence belongs in temporary drafts, and archived history is enough without soft deletion.
  Date/Author: 2026-06-24 / User and Codex

- Decision: Run only infrastructure in Docker during local development; run `bot` and `worker` directly on the computer with `uv`.
  Rationale: The user wants an easy local-debug loop without rebuilding a Docker image for every application change. PostgreSQL remains isolated and reproducible in Docker Compose, while the Python app uses the local `.env` and `.venv`.
  Date/Author: 2026-06-24 / User and Codex

- Decision: Keep enum vocabulary outside `storage.models` and explicitly map enum values in ORM columns.
  Rationale: Reminder, draft, delivery, and callback states are domain language that services reason about. The database layer should map that language to PostgreSQL types without owning the vocabulary.
  Date/Author: 2026-06-24 / User and Codex

- Decision: Use repository classes grouped by a Unit of Work for application service persistence.
  Rationale: Services should coordinate business behavior while repositories own SQLAlchemy queries. The Unit of Work gives each bot update or worker job one clear transaction boundary without sharing a global mutable `AsyncSession`.
  Date/Author: 2026-06-24 / User and Codex

- Decision: Use an input strategy boundary for reminder intake.
  Rationale: Text is the MVP input source. Future voice input can become a separate strategy that transcribes audio and then reuses the same parser, confidence layer, draft storage, and reminder service flow.
  Date/Author: 2026-06-24 / Codex

- Decision: The first draft-flow implements `confirm` and `cancel` only, while omitting edit-time and edit-text buttons from the confirmation keyboard.
  Rationale: This keeps the first Telegram-facing creation loop complete and testable without introducing a half-built edit state machine. Edit flows remain planned follow-up work.
  Date/Author: 2026-06-26 / Codex

- Decision: Split reminder application services by workflow while preserving `nudge_bot.reminders.service` as a thin compatibility facade.
  Rationale: Text intake, draft confirmation, fired-reminder actions, and worker claiming have different owners and test surfaces. Class-based modules keep dependency injection straightforward without forcing handlers or workers to know SQLAlchemy details.
  Date/Author: 2026-06-26 / Codex

- Decision: The first worker implementation sends fired reminders and handles `Read`/`Repeat`, while `Choose time` remains a placeholder and no-action auto-repeat is deferred.
  Rationale: Delivery and button idempotency are the smallest end-to-end slice needed to manually test reminders in Telegram. The edit-time state machine and unattended repeat policy can be added after the delivery path is observable and tested.
  Date/Author: 2026-06-26 / Codex

- Decision: Auto-repeat reuses `reminders.due_at` as the next fire time for delivered reminders.
  Rationale: A delivered one-off reminder that remains `sent` still needs one next scheduler timestamp. Reusing `due_at` keeps the MVP schema small, avoids introducing recurring-reminder concepts, and lets `Read` stop repeats by moving the reminder to `completed`.
  Date/Author: 2026-06-28 / Codex

- Decision: `Choose time` stores edit state in `drafts` with `type = reminder_edit_time` and a small JSON payload containing the reminder id, notification id, callback key, and display timezone.
  Rationale: The schema already includes durable drafts and the required draft enum value, so no migration is needed. Keeping the edit state in PostgreSQL makes the flow survive process restarts and keeps Telegram handlers thin.
  Date/Author: 2026-06-28 / Codex

- Decision: A successful `Choose time` edit moves the reminder to `snoozed`.
  Rationale: The user is explicitly postponing an already delivered reminder to a chosen future time. Using `snoozed` removes the old `sent` auto-repeat timestamp from the active loop while preserving the same one-off reminder record.
  Date/Author: 2026-06-28 / Codex

- Decision: The `Choose time` prompt is a normal chat message with a single `Cancel` button, not a Telegram popup alert.
  Rationale: A visible message can show an example input and gives the user a clear cancellation affordance. Cancelling closes the durable edit draft and deletes only the prompt message, leaving the fired reminder message and its action buttons intact.
  Date/Author: 2026-06-28 / Codex

- Decision: Suppress due claiming with a pending edit-time draft rather than adding a new reminder status.
  Rationale: The MVP enum already has a small lifecycle and no migration is needed for a new state. A scheduler-side exclusion keyed by the durable draft expresses that the reminder is temporarily waiting for user input, while cancellation, confirmation, or draft expiry naturally returns the reminder to normal scheduler behavior.
  Date/Author: 2026-06-28 / Codex

- Decision: Add a partial unique index for pending edit-time drafts per user.
  Rationale: Query-level reuse is not enough under concurrent callback delivery. The index makes the durable invariant explicit: one user can have only one pending edit-time session consuming the next text message.
  Date/Author: 2026-06-28 / Codex

- Decision: Serialize edit-time draft creation by locking the user row.
  Rationale: The partial unique index protects the database invariant, but locking the user before checking or creating pending edit-time drafts prevents concurrent `Choose time` callbacks for different reminders from surfacing as a generic uniqueness failure.
  Date/Author: 2026-06-28 / Codex

- Decision: Centralize edit-time draft payload keys in `nudge_bot.reminders.draft_payloads`.
  Rationale: Scheduler suppression depends on the reminder id stored in draft JSON. A helper keeps the service writer and scheduler reader aligned while preserving the MVP schema.
  Date/Author: 2026-06-28 / Codex

- Decision: Treat voice input as the next milestone after `Choose time` stabilization, implemented as an input strategy rather than a forked reminder lifecycle.
  Rationale: The text parser, confidence layer, draft confirmation flow, reminder service, UTC storage rules, and worker path are already the durable creation pipeline. Voice should add transcription and metadata at the input boundary, then hand the transcript to the same pipeline.
  Date/Author: 2026-06-28 / Codex

- Decision: Use local `faster-whisper` for first voice transcription with default model `base`, compute type `int8`, device `cpu`, and language `ru`.
  Rationale: This keeps voice input private-first and avoids sending audio to an external API. The defaults balance quality and local CPU cost for short Telegram reminder messages.
  Date/Author: 2026-06-28 / User and Codex

- Decision: Cap MVP voice reminders at 15 seconds and use fast local Whisper decoding.
  Rationale: Nudge is speed-first. Short reminder commands should either transcribe quickly or ask the user for a shorter voice message instead of making the chat feel stalled.
  Date/Author: 2026-06-30 / User and Codex

## Outcomes & Retrospective

The project is no longer only a planning shell. It now has a uv-compatible Python package, bot and worker entrypoints, pydantic settings, Docker Compose infrastructure for PostgreSQL, SQLAlchemy models with explicit PostgreSQL enum mappings, repository classes, a Unit of Work boundary, Alembic migrations for the documented schema, a project-owned parser rule layer, class-based reminder services, MVP draft-flow behavior, aiogram text/draft handlers, worker delivery, fired-reminder callbacks, unattended auto-repeat, a text-based `Choose time` edit flow, and local voice/audio reminder intake. The bot can now create active reminders from confident text or voice parses, create confirmation drafts from uncertain text or voice parses, deliver due reminders, complete delivered reminders with `Read`, snooze them with `Repeat`, ask for a new time through `Choose time`, reschedule the existing reminder from the user's next text message, and automatically re-send delivered reminders after the configured repeat interval when the user does nothing.

## Context and Orientation

This repository is currently a greenfield Telegram bot project. `AGENTS.md` records project-wide instructions, selected stack, and bot development practices. `.agent/PLANS.md` defines the required format and maintenance rules for ExecPlans. `.omx/specs/deep-interview-tg-reminder-bot.md` records the product requirements and UX flow discovered during the interview. `docs/database-schema.md` records the shared database schema direction and ER diagram.

A reminder is a durable record with `reminder_text`, a due time, a user owner, and a status. Durable means it is stored in PostgreSQL and survives process restarts.

Long polling means the bot process repeatedly asks Telegram for new updates through the Bot API. It is simple for local development because it does not require a public HTTPS URL.

A webhook means Telegram sends updates to our public HTTPS endpoint. It is useful in production because Telegram pushes updates to us, but it requires a web server, a public domain, TLS, and request verification.

A DB-backed polling worker is a process that periodically queries PostgreSQL for reminders whose due time has arrived. It does not keep the schedule only in memory. The database remains the source of truth.

Idempotent means repeating the same action is safe. If a user taps `Read` twice, the reminder remains completed once; it does not create duplicate history or corrupt state.

A repository is a small class that owns database queries for one group of records, such as users or reminders. A Unit of Work owns one database session and exposes repositories for one transaction, such as one bot update or one worker batch.

An input strategy is a small object that knows how to turn one kind of user input into a parsed reminder draft. Text input passes text directly to the parser. Voice input transcribes Telegram voice/audio first and then reuses the same parser and reminder service path.

## Plan of Work

Milestone 1 creates the project foundation. Add `pyproject.toml`, `src/nudge_bot`, `tests`, Ruff configuration, uv-compatible dependencies, a `.env.example`, and a small settings module. The repository should be able to install dependencies, run linting, and run an empty test suite.

Milestone 2 adds local infrastructure. Add `docker-compose.yml` with PostgreSQL only. The Python application should run directly on the developer's computer through uv: `uv run nudge-bot` for Telegram long polling and `uv run nudge-worker` for reminder scheduling.

Milestone 3 adds persistence. Define SQLAlchemy models and Alembic migrations for users, user settings, reminders, reminder attempts, drafts, and callback events. All rows that belong to a Telegram user must be scoped by `telegram_user_id` or internal `user_id`. Bounded values such as reminder status, reminder type, delivery status, draft type, draft status, callback action, and callback event status must use PostgreSQL enum types.

Persistence code should be reached through repository classes and `storage.unit_of_work.UnitOfWork`. Do not add new SQLAlchemy queries directly to bot handlers. Application services may coordinate repositories, but storage-specific query details belong in repositories.

Milestone 4 implements parsing. Add a parser service that accepts user input text and returns a draft containing final candidate reminder text, parsed due time, parse confidence, source type, and intent kind. Use `dateparser` as a helper, but keep project-owned confidence rules around it. Confidence is temporary and should be stored only in `drafts` when confirmation is needed, not on final `reminders` rows.

Milestone 5 implements bot interaction. Add aiogram routers for `/start`, free text messages, confirmation actions, settings, active reminders, and history. Use aiogram CallbackData classes for button payloads such as read, repeat, choose time, confirm, edit, and cancel.

Milestone 6 implements the worker. The worker should periodically claim due reminders from PostgreSQL, send Telegram notifications, record delivery attempts, and schedule the next repeat if the user does not act. Use UTC timestamps in the database and user timezone only at input/output boundaries.

Milestone 7 hardens behavior. Add idempotency around callback handlers, basic per-user button throttling, Telegram API retry handling, structured logging without full reminder text by default, and tests for the state machine.

Milestone 8 adds voice input as a new reminder intake strategy. The bot should accept Telegram voice/audio messages, download the file through the Telegram adapter, transcribe it through a small transcription boundary, and pass the transcript into the same parser and reminder intake flow as text messages. Store the final reminder as `source_type = voice` and keep transcript/source metadata in `reminders.metadata` or `drafts.payload` without storing unnecessary raw audio.

Voice input design checkpoints before implementation:

1. Choose the transcription dependency and configuration surface, including local-development behavior when credentials are missing.
2. Define a `VoiceReminderInputStrategy` or equivalent service boundary that returns transcript text plus metadata, then delegates to the existing text parser/intake path.
3. Keep aiogram voice/audio handlers thin: fetch Telegram file metadata, call the voice service, and render the same created/draft/unknown responses already used for text.
4. Add narrow unit tests for transcript handoff, metadata persistence shape, unsupported/failed transcription responses, and reuse of the existing confirmation flow.
5. Do not add Redis, APScheduler, FastAPI, webhooks, recurring reminders, or a separate voice-only reminder lifecycle for this milestone.

## Concrete Steps

Run all commands from `C:\Users\sqd12\Documents\Nudge`.

First scaffold the project:

    uv init --package
    uv add aiogram sqlalchemy asyncpg alembic pydantic-settings dateparser
    uv add --dev pytest pytest-asyncio ruff

The scaffold is now checked in manually with the same dependency set in `pyproject.toml`. In the Codex Windows App environment used on 2026-06-24, the working validation command used the bundled Python and a repository-local uv cache:

    $env:UV_CACHE_DIR = "C:\Users\sqd12\Documents\Nudge\.uv-cache"
    C:\Users\sqd12\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m uv run pytest

Create `src/nudge_bot/config.py` with a pydantic-settings `Settings` class that reads `BOT_TOKEN`, `DATABASE_URL`, `DEFAULT_TIMEZONE`, `DEFAULT_REPEAT_INTERVAL_MINUTES`, `SCHEDULER_POLL_INTERVAL_SECONDS`, and `LOG_LEVEL`.

Create entrypoints:

    src/nudge_bot/bot/main.py
    src/nudge_bot/worker/main.py

The bot entrypoint starts aiogram long polling. The worker entrypoint starts an async loop that sleeps for `SCHEDULER_POLL_INTERVAL_SECONDS` between due-reminder scans.

Create database modules:

    src/nudge_bot/storage/database.py
    src/nudge_bot/storage/models.py
    src/nudge_bot/storage/repositories/
    src/nudge_bot/storage/unit_of_work.py

Initialize Alembic and create the first migration:

    uv run alembic init alembic
    uv run alembic revision --autogenerate -m "create reminder tables"
    uv run alembic upgrade head

Create parser and domain modules:

    src/nudge_bot/reminders/parser.py
    src/nudge_bot/reminders/intake.py
    src/nudge_bot/reminders/domain.py
    src/nudge_bot/reminders/enums.py
    src/nudge_bot/reminders/service.py

Create Telegram adapter modules:

    src/nudge_bot/bot/routers/start.py
    src/nudge_bot/bot/routers/reminders.py
    src/nudge_bot/bot/callbacks.py
    src/nudge_bot/bot/keyboards.py

Add tests as modules are introduced:

    uv run pytest
    uv run ruff check .
    uv run ruff format --check .

Expected final validation transcript should look like:

    uv run pytest
    N passed

    uv run ruff check .
    All checks passed!

    docker compose up -d postgres

    uv run nudge-bot
    bot: polling started

    uv run nudge-worker
    worker: scheduler started

Current scaffold validation transcript:

    python -m uv run pytest
    8 passed

    python -m uv run ruff check .
    All checks passed!

    python -m uv run ruff format --check .
    38 files already formatted

## Validation and Acceptance

The implementation is accepted when a developer can run PostgreSQL through Docker Compose, start the local bot and worker processes with uv, send a text reminder to the Telegram bot, and observe the notification arrive after the parsed time.

The user-visible acceptance cases are:

1. Sending "walk the dog in 20 minutes" creates a reminder and sends a confirmation.
2. Sending a date/time phrase with uncertain parsing asks for confirmation instead of silently creating a wrong reminder.
3. When a reminder is due, the bot sends inline buttons for `Read`, `Repeat`, and `Choose time`.
4. Pressing `Read` marks the reminder completed and stops future repeats.
5. Pressing `Repeat` schedules the reminder again after the configured interval.
6. Pressing `Choose time`, then sending "через 20 минут" or "tomorrow at 9", reschedules the same reminder to the parsed time without changing the reminder text.
7. Pressing `Read` twice remains safe and does not duplicate state.
8. If the user does not press any button after a delivered notification, the worker sends the same reminder again after the user's configured repeat interval.
9. If the worker restarts, reminders stored in PostgreSQL are still found and delivered.

The technical acceptance cases are:

1. Tests cover parser confidence behavior.
2. Tests cover reminder status transitions.
3. Tests cover idempotent callback handling.
4. Tests cover worker claiming so the same due reminder is not sent twice by one scan.
5. Tests cover auto-repeat scheduling from successful delivery and due claiming of `sent` reminders.
6. Tests cover `Choose time` draft creation, repeated-button idempotency, parsing a replacement time, low-confidence/unknown input, and expired edit drafts.
7. Ruff lint and format checks pass.

## Idempotence and Recovery

All setup commands should be safe to rerun. Docker Compose can recreate local containers from the checked-in configuration. Alembic migrations should be additive and reversible during development where practical.

If Telegram delivery fails, record the failure in `reminder_attempts` and schedule a delivery retry without changing the user's reminder into a completed state.

If the bot crashes after claiming a due reminder but before sending it, the claim must expire or be recoverable. A practical MVP approach is to include `locked_at` and treat old locks as abandoned after a short timeout.

If a user taps an old inline button, the handler should load current reminder state and answer gracefully. For example, if the reminder is already completed, the bot should say that it is already handled instead of failing.

## Artifacts and Notes

The selected stack is recorded in `AGENTS.md` and `README.md`. Any future stack change must update both this ExecPlan and `AGENTS.md`.

The database schema direction is recorded in `docs/database-schema.md`. Any schema implementation should keep that file current so future chats can continue from the same database picture.

The first migration should include the indexes documented in `docs/database-schema.md`, especially the due-reminder worker index, callback idempotency index, pending draft indexes, and user history indexes.

The short continuation handoff is recorded in `docs/handoff.md`.

The product source of truth is `.omx/specs/deep-interview-tg-reminder-bot.md`.

The implementation should keep the MVP private-first and free. Do not add payments, ads, recurring reminders, or a full idea inbox in this milestone.

## Interfaces and Dependencies

Use these dependencies:

- `aiogram` for Telegram Bot API integration.
- `sqlalchemy` with its asyncio API for database models and queries.
- `asyncpg` as the PostgreSQL driver.
- `alembic` for schema migrations.
- `pydantic-settings` for environment-driven configuration.
- `dateparser` for natural language date parsing.
- `faster-whisper` for local Telegram voice/audio transcription.
- `pytest` and `pytest-asyncio` for tests.
- `ruff` for linting and formatting.

Define a parser contract in `src/nudge_bot/reminders/parser.py`:

    class ParsedReminderDraft:
        input_text: str
        reminder_text: str | None
        due_at: datetime | None
        parse_confidence: float
        intent_kind: ParserIntent
        needs_confirmation: bool

    def parse_reminder_text(text: str, *, now: datetime, timezone: str) -> ParsedReminderDraft:
        ...

Define callback data classes in `src/nudge_bot/bot/callbacks.py` using aiogram `CallbackData`:

    class ReminderActionCallback(CallbackData, prefix="rem"):
        action: Literal["read", "repeat", "choose_time"]
        reminder_id: int
        notification_id: int | None = None

    class ReminderDraftCallback(CallbackData, prefix="draft"):
        action: Literal["confirm", "edit_time", "edit_text", "cancel"]
        draft_id: int

Define a worker service in `src/nudge_bot/reminders/service.py`:

    async def claim_due_reminders(uow: UnitOfWork, *, limit: int, now: datetime) -> list[ReminderToSend]:
        ...

    async def mark_completed(uow: UnitOfWork, *, reminder_id: int, user_id: int) -> ReminderResult:
        ...

    async def snooze(uow: UnitOfWork, *, reminder_id: int, user_id: int, interval_minutes: int) -> ReminderResult:
        ...

`ReminderToSend` in `src/nudge_bot/reminders/domain.py` must include `repeat_interval_minutes`. The worker gets that value from `user_settings` during due claiming and passes it to `ReminderDeliveryService.mark_sent`, which moves `reminders.due_at` to the next auto-repeat time after Telegram accepts a notification.

Best practices that must hold during implementation:

- Keep aiogram handlers thin and route real behavior to services.
- Store durable state in PostgreSQL, not process memory.
- Store timestamps in UTC.
- Scope all user data by user id.
- Use typed callback data classes.
- Make button actions idempotent.
- Separate Telegram delivery retries from user-facing reminder repeats.
- Avoid logging full reminder text by default.
- Write domain tests before relying on manual Telegram testing.

Voice input must not fork the reminder lifecycle. It turns Telegram voice/audio into text plus metadata, then routes the transcript through the same parser, draft confirmation, reminder service, and persistence flow used by text reminders.

Revision note: Initial ExecPlan created to capture the selected Python stack, MVP scope, architecture, best practices, validation path, and future stack-change rule.

Revision note: Scaffold implementation started on 2026-06-24. The plan now records the created Python package, Docker/Alembic/config artifacts, the initial parser test result, and the environment-specific uv cache workaround used for validation.

Revision note: Local development workflow revised on 2026-06-24. Docker Compose now owns only PostgreSQL infrastructure, while `bot` and `worker` run locally through uv for faster debugging.

Revision note: Architecture boundaries revised on 2026-06-24. Enum vocabulary moved out of ORM models, ORM enum columns now explicitly match PostgreSQL enum names and values, storage access is grouped behind repositories, services use a Unit of Work, and text reminder intake now has a strategy boundary for future voice support.

Revision note: Index metadata aligned on 2026-06-24. The baseline migration remains the source for creating the documented indexes, and SQLAlchemy models now declare the same non-column indexes for readability and future Alembic autogeneration.

Revision note: Auto-repeat implemented on 2026-06-28. Delivered reminders now keep status `sent` while `due_at` is moved to the next unattended repeat time, the due-reminder index includes `sent`, and `ReminderToSend` carries `repeat_interval_minutes` from `user_settings`.

Revision note: Choose-time edit flow implemented on 2026-06-28. Pressing `Choose time` now creates or reuses a durable `reminder_edit_time` draft, sends a normal prompt message with a `Cancel` button, parses the next text message with the existing reminder parser, and moves the same reminder to `snoozed` at the chosen UTC due time after a successful edit.

Revision note: Choose-time review fixes applied on 2026-06-28. Pending edit-time drafts now suppress due claiming until cancellation, confirmation, or expiry; reminder rows are locked before edit application; duplicate pending edit-time drafts are prevented by a partial unique index; repeated `Choose time` taps no longer send duplicate prompt messages.

Revision note: Choose-time follow-up hardening applied on 2026-06-28. The edit-time payload contract is centralized, pending draft creation serializes on the user row, the duplicate-draft migration cleans up older pending duplicates before creating the unique index, and README reflects the implemented text-based `Choose time` flow.

Revision note: Choose-time test stabilization completed on 2026-06-28. A focused unit test now covers replacing a pending edit-time draft for another reminder, full validation is green with 71 tests, and the plan now points to voice input as the next input-strategy milestone.

Revision note: Voice input implemented on 2026-06-28. Telegram voice/audio is downloaded by the bot route, transcribed locally with `faster-whisper`, processed through shared source-aware reminder intake, and stored as voice-sourced reminders or drafts with minimal transcript metadata.

Revision note: Voice validation on 2026-06-28 used the existing `.venv` because network access to PyPI was denied while resolving `faster-whisper` for `uv run`. Update `uv.lock` and run `uv sync` once network access is available.

Revision note: Voice performance pass on 2026-06-30 changed the default local model to `base`, added `VOICE_MAX_DURATION_SECONDS`, warmed the local transcriber at bot startup, enabled fast `faster-whisper` transcribe options, and added a `Transcribing...` Telegram progress message.
