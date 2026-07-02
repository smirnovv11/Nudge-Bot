# Northflank Deployment

This project deploys as one Docker image and two long-running services:

- `nudge-bot`: receives Telegram updates through long polling.
- `nudge-worker`: polls PostgreSQL for due reminders and sends notifications.

Use one shared PostgreSQL database. Do not run more than one `nudge-bot` replica with the same
Telegram token while the MVP uses long polling.

## Northflank Setup

1. Create a Northflank project and a PostgreSQL database addon.
2. Create a service named `nudge-bot` from an external image:
   `ghcr.io/<github-owner>/nudge-bot:latest`.
3. Set the bot service command to:

   ```sh
   nudge-bot
   ```

4. Create a second service named `nudge-worker` from the same image.
5. Set the worker service command to:

   ```sh
   nudge-worker
   ```

6. Add the same environment variables to both services:

   ```env
   BOT_TOKEN=123456:telegram-token-from-botfather
   DATABASE_URL=postgresql+asyncpg://user:password@host:5432/database?sslmode=require
   DEFAULT_TIMEZONE=Europe/Minsk
   DEFAULT_REPEAT_INTERVAL_MINUTES=5
   SCHEDULER_POLL_INTERVAL_SECONDS=10
   LOG_LEVEL=INFO
   VOICE_TRANSCRIPTION_MODEL=base
   VOICE_TRANSCRIPTION_COMPUTE_TYPE=int8
   VOICE_TRANSCRIPTION_DEVICE=cpu
   VOICE_TRANSCRIPTION_LANGUAGE=ru
   VOICE_MAX_FILE_SIZE_MB=20
   VOICE_MAX_DURATION_SECONDS=15
   ```

   Northflank can provide a PostgreSQL URL with `sslmode=require`. Keep that query parameter if it
   appears; the application translates it to the `asyncpg` SSL option at startup.

7. Add this only to the `nudge-bot` service:

   ```env
   RUN_MIGRATIONS=true
   ```

   Leave it unset or set to `false` on `nudge-worker`.

8. Add this only to the `nudge-worker` service:

   ```env
   WAIT_FOR_MIGRATIONS=true
   ```

   This lets CI trigger both deployments back-to-back while the worker waits until the shared
   database has reached the image's Alembic head before starting the scheduler loop.

## GitHub Secrets

The GitHub Actions workflow builds and pushes the image to GitHub Container Registry, then triggers
Northflank deployment hooks.

Create these repository secrets:

- `NORTHFLANK_BOT_DEPLOY_HOOK_URL`: deployment hook URL for the bot service.
- `NORTHFLANK_WORKER_DEPLOY_HOOK_URL`: deployment hook URL for the worker service.

GitHub's built-in `GITHUB_TOKEN` is used to push the image to GHCR. If the Northflank services cannot
pull the image, make the package public or configure Northflank with registry credentials for GHCR.

## Deployment Flow

1. Open a pull request.
2. GitHub Actions runs Ruff, format check, tests, and a Docker build.
3. Merge to `main`.
4. GitHub Actions builds and pushes `latest` and commit-SHA image tags.
5. GitHub Actions calls the two Northflank deployment hooks.
6. Northflank redeploys `nudge-bot`; the entrypoint runs Alembic migrations, then starts polling.
7. Northflank redeploys `nudge-worker`; it starts the scheduler loop without running migrations.

## Smoke Test

After deployment:

1. Open Northflank logs for both services.
2. Send `/start` to the Telegram bot.
3. Send a text reminder such as `test in 2 minutes`.
4. Confirm the worker sends the reminder and the action buttons work.
5. Send a short voice reminder and confirm transcription still fits the free instance.
