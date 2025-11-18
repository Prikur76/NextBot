#!/bin/bash
set -e

echo "=== Starting NextBot Initialization ==="

# Ожидание доступности PostgreSQL
echo "⏳ Waiting for PostgreSQL..."
max_attempts=30
attempt=1

while ! nc -z $POSTGRES_HOST 5432; do
    if [ $attempt -eq $max_attempts ]; then
        echo "❌ PostgreSQL not available after $max_attempts attempts. Exiting."
        exit 1
    fi
    echo "📡 Attempt $attempt/$max_attempts: PostgreSQL not ready, retrying in 2s..."
    sleep 2
    attempt=$((attempt + 1))
done

echo "✅ PostgreSQL started successfully"

# Выполнение миграций
echo "🔄 Running database migrations..."
python manage.py migrate

# Создание статических файлов
echo "📦 Collecting static files..."
python manage.py collectstatic --noinput

# Создание суперпользователя (опционально)
if [ "$CREATE_SUPERUSER" = "true" ]; then
    echo "👑 Creating superuser..."
    export DJANGO_SUPERUSER_USERNAME=${ADMIN_USERNAME:-admin}
    export DJANGO_SUPERUSER_EMAIL=${ADMIN_EMAIL:-admin@example.com}
    export DJANGO_SUPERUSER_PASSWORD=${ADMIN_PASSWORD:-admin}
    python manage.py createsuperuser --noinput || echo "⚠️ Superuser already exists or creation failed"
fi

echo "🎉 Initialization completed successfully!"
