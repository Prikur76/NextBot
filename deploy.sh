#!/bin/bash
set -e

# Загружаем переменные окружения из .env (DOMAIN, LETSENCRYPT_EMAIL)
export $(grep -v '^#' .env | xargs)

COMPOSE="docker compose -f docker-compose.prod.yml"

echo "====================================================="
echo " 🚀 Starting Deployment for $DOMAIN" | tee -a $LOGFILE
echo "====================================================="

rollback() {
    echo "[ERROR] Deployment failed! Rolling back..." | tee -a $LOGFILE
    $COMPOSE down
    git reset --hard HEAD
    echo "Rollback complete." | tee -a $LOGFILE
    exit 1
}

trap rollback ERR

echo "🔄 Pulling latest code..." | tee -a $LOGFILE
git fetch --all
git reset --hard origin/main

echo ""
echo "🛠 Building images..." | tee -a $LOGFILE
$COMPOSE build --no-cache

echo ""
echo "🚀 Starting containers..." | tee -a $LOGFILE
$COMPOSE up -d

echo ""
echo "⏳ Waiting for web to start..." | tee -a $LOGFILE
sleep 5

echo ""
echo "🗄 Applying migrations..." | tee -a $LOGFILE
$COMPOSE exec web python manage.py migrate --noinput

echo ""
echo "📦 Collecting static files..." | tee -a $LOGFILE
$COMPOSE exec web python manage.py collectstatic --noinput

echo ""
echo "🧹 Cleaning unused docker resources..." | tee -a $LOGFILE
docker system prune -f

echo ""
echo "🏃 Checking health of services..." | tee -a $LOGFILE
sleep 5
docker ps | grep $DOMAIN

echo ""
echo "🔐 Obtaining / Renewing SSL certificates..." | tee -a $LOGFILE
$COMPOSE run --rm certbot certonly \
  --webroot -w /var/www/certbot \
  -d $DOMAIN \
  --email $LETSENCRYPT_EMAIL \
  --agree-tos \
  --no-eff-email


echo ""
echo "🔄 Restarting nginx to apply new SSL certs..." | tee -a $LOGFILE
$COMPOSE restart nginx

echo ""
echo "====================================================="
echo " ✨ Deployment complete!" | tee -a $LOGFILE
echo "=====================================================" | tee -a $LOGFILE
