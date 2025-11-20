#!/bin/bash
set -e

echo "⏳ Waiting for PostgreSQL..."
python scripts/wait-for-db.py

echo "🚀 Starting Gunicorn..."
exec gunicorn nextbot.asgi:application \
    -k uvicorn.workers.UvicornWorker \
    --workers 4 \
    --bind 0.0.0.0:8000 \
    --log-level info
