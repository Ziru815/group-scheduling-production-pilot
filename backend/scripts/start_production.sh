#!/bin/sh
set -eu

alembic upgrade head
python -m scripts.seed_reference_data

case "${VENUE_SYNC_MODE:-}" in
  "")
    ;;
  dry-run)
    python -m scripts.sync_venues --dry-run
    ;;
  apply)
    python -m scripts.sync_venues --apply
    ;;
  *)
    echo "Invalid VENUE_SYNC_MODE: expected dry-run, apply, or empty." >&2
    exit 64
    ;;
esac

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-10000}"
