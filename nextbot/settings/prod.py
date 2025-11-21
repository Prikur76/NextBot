"""Production settings - sensitive and strict.

This file expects required environment variables to be present and will
raise clear errors if critical values are missing.
"""
import dj_database_url
from .base import *

# Ensure DEBUG off
DEBUG = False

# Hosts - require explicit value in env
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["127.0.0.1", "localhost",], delimiter=",")

# Database
DATABASE_URL = env.str("DATABASE_URL", None)

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL must be set in production")

DATABASES = {
    "default": dj_database_url.parse(
        DATABASE_URL,
        engine="django.db.backends.postgresql",
        conn_max_age=600,
        conn_health_checks=True,
        ssl_require=env.bool("DB_SSL_REQUIRE", False),
    )
}

# Security hardening
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", True)
SESSION_COOKIE_SECURE = env.bool("SESSION_COOKIE_SECURE", True)
CSRF_COOKIE_SECURE = env.bool("CSRF_COOKIE_SECURE", True)
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", 31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", True)
SECURE_HSTS_PRELOAD = env.bool("SECURE_HSTS_PRELOAD", True)

# Running behind a proxy/load balancer
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True
USE_X_FORWARDED_PORT = True

# Email: use real SMTP
EMAIL_BACKEND = env.str("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")

# Logging: more strict
LOGGING["handlers"]["file_general"]["maxBytes"] = 100 * 1024 * 1024
LOGGING["handlers"]["file_general"]["backupCount"] = 10
LOGGING["handlers"]["file_errors"]["backupCount"] = 180
LOGGING["root"]["handlers"] = ["file_general", "file_errors", "mail_admins"]
LOGGING["root"]["level"] = "INFO"

# Admin emails must be explicitly set
if not ADMINS:
    raise RuntimeError("ADMINS is empty — set DJANGO_SUPERUSER_* env vars")