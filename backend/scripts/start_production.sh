#!/bin/sh
set -eu

alembic upgrade head
python -m scripts.seed_reference_data
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-10000}"
