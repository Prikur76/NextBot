FROM python:3.12-slim

# OS deps
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    libpq-dev \
    curl \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install Python deps
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Create non-root user
RUN useradd -m appuser

# Copy source
COPY . /app

# Устанавливаем права на logs и весь /app
RUN mkdir -p /app/logs && chown -R appuser:appuser /app
# Устанавливаем права на static
RUN mkdir -p /app/staticfiles && chown -R appuser:appuser /app/staticfiles

# Переходим на non-root пользователя
USER appuser

# Исполняемые скрипты
RUN chmod +x /app/scripts/entrypoint.sh
RUN chmod +x /app/scripts/wait-for-db.py

ENTRYPOINT ["/app/scripts/entrypoint.sh"]
