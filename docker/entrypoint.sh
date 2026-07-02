#!/bin/sh
set -eu

wait_for_migrations() {
  head_revision="$(alembic heads | awk '{print $1}')"
  attempts="${MIGRATION_WAIT_ATTEMPTS:-60}"
  sleep_seconds="${MIGRATION_WAIT_SECONDS:-2}"

  i=1
  while [ "$i" -le "$attempts" ]; do
    current_revision="$(alembic current 2>/dev/null | awk '{print $1}' || true)"
    if [ "$current_revision" = "$head_revision" ]; then
      return 0
    fi

    echo "Waiting for database migrations: current=${current_revision:-none}, head=$head_revision"
    sleep "$sleep_seconds"
    i=$((i + 1))
  done

  echo "Database did not reach Alembic head $head_revision before timeout" >&2
  return 1
}

if [ "${RUN_MIGRATIONS:-false}" = "true" ]; then
  alembic upgrade head
fi

if [ "${WAIT_FOR_MIGRATIONS:-false}" = "true" ]; then
  wait_for_migrations
fi

exec "$@"
