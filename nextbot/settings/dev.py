"""Development settings - extend base with dev-friendly defaults."""
from .base import *


# Make sure DEBUG is True
DEBUG = True

# Allow all hosts locally
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["127.0.0.1", "localhost"], delimiter=",")

# Use sqlite by default in dev
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# Keep console logging in dev
LOGGING["root"]["handlers"] = ["console", "file_general"]
LOGGING["root"]["level"] = "DEBUG"

# Email to console in dev to avoid accidental sends
EMAIL_BACKEND = env.str("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")

# Relax security for local dev
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_HSTS_SECONDS = 0
SECURE_PROXY_SSL_HEADER = None
USE_X_FORWARDED_HOST = False

# Use local cache in dev
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-nextbot',
    }
}
