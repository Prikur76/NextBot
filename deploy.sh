#!/bin/bash
set -e

# Загружаем переменные окружения из .env (DOMAIN, LETSENCRYPT_EMAIL)
export $(grep -v '^#' .env | xargs)

COMPOSE="docker compose -f docker-compose.prod.yml"

echo "====================================================="
echo " 🚀 Starting Deployment for $DOMAIN"
echo "====================================================="

echo ""
echo "🔄 Pulling latest code..."
git pull origin main

echo ""
echo "🛠 Building images..."
$COMPOSE build --no-cache

echo ""
echo "🚀 Starting containers..."
$COMPOSE up -d

echo ""
echo "⏳ Waiting for web to start..."
sleep 5

echo ""
echo "🗄 Applying migrations..."
$COMPOSE exec web python manage.py migrate --noinput

echo ""
echo "📦 Collecting static files..."
$COMPOSE exec web python manage.py collectstatic --noinput

echo ""
echo "🔐 Obtaining / Renewing SSL certificates..."
$COMPOSE run --rm certbot certonly \
  --webroot -w /var/www/certbot \
  -d $DOMAIN \
  --email $LETSENCRYPT_EMAIL \
  --agree-tos \
  --no-eff-email

echo ""
echo "♻️ Reloading nginx..."
$COMPOSE exec nginx nginx -s reload

echo ""
echo "====================================================="
echo " ✨ Deployment complete!"
echo "====================================================="
