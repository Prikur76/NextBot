#!/bin/bash
set -e

echo "⏳ Waiting for PostgreSQL..."
python scripts/wait-for-db.py

echo "🔄 Running migrations..."
python manage.py migrate --noinput

echo "🔐 Creating superuser..."
python manage.py create_superuser

echo "📦 Collecting static (dev)..."
python manage.py collectstatic --noinput

echo "🚀 Starting Uvicorn with hot reload..."
exec uvicorn nextbot.asgi:application \
    --host 0.0.0.0 \
    --port 8000 \
    --reload
