#!/bin/bash
set -e

echo "⏳ Waiting for PostgreSQL..."
python scripts/wait-for-db.py

echo "⚙️ Applying migrations..."
python manage.py migrate --noinput

echo "📦 Collecting static files..."
python manage.py collectstatic --noinput

if [ "$DJANGO_SUPERUSER_USERNAME" ] && [ "$DJANGO_SUPERUSER_EMAIL" ] && [ "$DJANGO_SUPERUSER_PASSWORD" ]; then
    echo "🔐 Creating superuser..."
    python manage.py createsuperuser --noinput || echo "Superuser already exists."
fi

echo "🚀 Starting Gunicorn..."
exec gunicorn nextbot.asgi:application \
    -k uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000 \
    --workers 4 \
    --log-level info
