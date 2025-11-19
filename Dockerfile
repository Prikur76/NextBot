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

# Copy source
COPY . /app

# Права на выполнение скриптов
RUN chmod +x /app/scripts/entrypoint.sh

# Создаём и даём права на logs
RUN mkdir -p /app/logs && chown -R appuser:appuser /app/logs

# Non-root user
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

ENTRYPOINT ["/app/scripts/entrypoint.sh"]
