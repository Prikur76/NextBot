#!/bin/bash
set -Eeuo pipefail

LOGFILE="deploy.log"
COMPOSE="docker compose -f docker-compose.prod.yml"

# Load environment variables from .env
export $(grep -v '^#' .env | xargs || true)

echo "=====================================================" | tee -a $LOGFILE
echo " 🚀 Starting Deployment for $DOMAIN" | tee -a $LOGFILE
echo "=====================================================" | tee -a $LOGFILE

############################################
# ROLLBACK
############################################
rollback() {
    echo ""
    echo "❗ ERROR: Deployment failed! Rolling back..." | tee -a $LOGFILE
    echo "Stopping containers..." | tee -a $LOGFILE
    $COMPOSE down -v || true
    echo "Resetting code..." | tee -a $LOGFILE
    git reset --hard HEAD~1 || true
    echo "✔ Rollback complete." | tee -a $LOGFILE
    exit 1
}
trap rollback ERR

############################################
# CHECK VOLUME PERMISSIONS
############################################
echo "🔍 Checking volume permissions..." | tee -a $LOGFILE

# logs: writable
mkdir -p ./logs
chmod 777 ./logs
echo "✔ ./logs is writable" | tee -a $LOGFILE

# local_secrets: read-only for container
mkdir -p ./local_secrets
echo "✔ ./local_secrets exists (read-only for container user)" | tee -a $LOGFILE

############################################
# UPDATE CODE
############################################
echo "🔄 Pulling latest code..." | tee -a $LOGFILE
git fetch origin
git reset --hard origin/main

############################################
# BUILD IMAGES
############################################
echo ""
echo "🛠 Building Docker images..." | tee -a $LOGFILE
$COMPOSE build

############################################
# START SERVICES
############################################
echo ""
echo "🚀 Starting containers..." | tee -a $LOGFILE
$COMPOSE up -d

############################################
# WAIT FOR WEB TO BE HEALTHY
############################################
echo ""
echo "⏳ Waiting for web to become healthy..." | tee -a $LOGFILE

CONTAINER_ID=$($COMPOSE ps -q web || true)
if [[ -z "$CONTAINER_ID" ]]; then
  echo "❌ Cannot find container id for service 'web'" | tee -a $LOGFILE
  $COMPOSE ps | tee -a $LOGFILE
  exit 1
fi

STATUS=""
for i in {1..30}; do
  STATUS=$(docker inspect --format='{{.State.Health.Status}}' "$CONTAINER_ID" 2>/dev/null || echo "unknown")
  echo "Check $i: web health status = $STATUS" | tee -a $LOGFILE
  if [[ "$STATUS" == "healthy" ]]; then
    echo "✔ Web is healthy!" | tee -a $LOGFILE
    break
  fi
  sleep 2
done

if [[ "$STATUS" != "healthy" ]]; then
  echo "❌ Web failed to become healthy (status=$STATUS)" | tee -a $LOGFILE
  docker inspect "$CONTAINER_ID" | tee -a $LOGFILE
  echo "Attempting HTTP /health check via nginx..." | tee -a $LOGFILE
  $COMPOSE exec --index 1 nginx sh -c 'curl -sS -I http://web:8000/health/ || true' | tee -a $LOGFILE
  exit 1
fi

############################################
# APPLY MIGRATIONS
############################################
echo ""
echo "🗄 Applying migrations..." | tee -a $LOGFILE
$COMPOSE exec web python manage.py migrate --noinput

############################################
# COLLECT STATIC FILES
############################################
echo ""
echo "📦 Collecting static files..." | tee -a $LOGFILE
$COMPOSE exec web python manage.py collectstatic --noinput

############################################
# CLEANUP
############################################
echo ""
echo "🧹 Cleaning unused docker resources..." | tee -a $LOGFILE
docker system prune -f >/dev/null 2>&1 || true

############################################
# CHECK MAIN SERVICES
############################################
echo ""
echo "🏃 Checking running services..." | tee -a $LOGFILE
required=("nextbot_web" "nextbot_nginx" "telegram_bot_prod" "scheduler_prod")

for svc in "${required[@]}"; do
    if docker ps --format '{{.Names}}' | grep -q "^$svc$"; then
        echo "✔ $svc is running" | tee -a $LOGFILE
    else
        echo "❌ $svc is NOT running!" | tee -a $LOGFILE
        exit 1
    fi
done

############################################
# SSL CERTIFICATES
############################################
echo ""
echo "🔐 Renewing SSL certificates (won't break deployment if fails)..." | tee -a $LOGFILE
$COMPOSE run --rm certbot renew --non-interactive || echo "⚠ SSL renewal failed or rate-limited, continuing..." | tee -a $LOGFILE

############################################
# RELOAD NGINX
############################################
echo ""
echo "🔄 Reloading nginx to apply certs..." | tee -a $LOGFILE
$COMPOSE restart nginx

############################################
# DONE
############################################
echo ""
echo "=====================================================" | tee -a $LOGFILE
echo " ✨ Deployment complete!" | tee -a $LOGFILE
echo "=====================================================" | tee -a $LOGFILE
