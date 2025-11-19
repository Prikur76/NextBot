"""Base settings shared by dev and prod.

Keep only settings that are environment-independent here.
"""
import os
from environs import Env
from pathlib import Path

from .logging_conf import LOGGING

# Environment
env = Env()
env.read_env()


# Build paths inside the project like this: BASE_DIR / "subdir".
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# SECURITY
SECRET_KEY = env.str("SECRET_KEY", "replace-me-with-secure-key")
DEBUG = env.bool("DEBUG", True)

ALLOWED_HOSTS = env.list(
    "ALLOWED_HOSTS", ["127.0.0.1", "localhost"] if DEBUG else ["refuel.txnxt.ru,"],
    delimiter=","
)

# Apps
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Third party
    "ninja",

    # Local
    "core",
]

AUTH_USER_MODEL = "core.User"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


ROOT_URLCONF = "nextbot.urls"
ASGI_APPLICATION = "nextbot.asgi.application"
WSGI_APPLICATION = "nextbot.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]


# Internationalization
LANGUAGE_CODE = "ru-RU"
TIME_ZONE = env.str("TIME_ZONE", "Europe/Moscow")
USE_I18N = True
USE_TZ = True


# Static & Media
STATICFILES_STORAGE = "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = []

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Default PK field
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# === Integrations / Custom settings ===
TELEGRAM = {"TOKEN": env.str("TELEGRAM_BOT_TOKEN", "")} # TELEGRAM['TOKEN']

ELEMENT_API = {
    "URL": env.str("ELEMENT_API_URL", ""),
    "USER": env.str("ELEMENT_API_USER", ""),
    "PASSWORD": env.str("ELEMENT_API_PASSWORD", ""),
}

GSHEET = {
    "CREDENTIALS_JSON_PATH": BASE_DIR / env.str("GSHEET_CREDENTIALS_JSON_PATH", ""),
    "SPREADSHEET_ID": env.str("GSHEET_SPREADSHEET_ID", ""),
    "SHEET_NAME": env.str("GSHEET_SHEET_NAME", ""),
}

SYNC_CARS_SCHEDULE_MINUTES = env.int("SYNC_CARS_SCHEDULE_MINUTES", 30)

# UX
CSRF_FAILURE_VIEW = "django.views.csrf.csrf_failure"
LOGIN_URL = "/admin/login/?next=/admin/"

# Email defaults (can be overridden in prod)
EMAIL_BACKEND = env.str("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = env.str("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = env.int("EMAIL_PORT", 587)
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", True)
EMAIL_HOST_USER = env.str("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env.str("EMAIL_HOST_PASSWORD", "")
SERVER_EMAIL = env.str("SERVER_EMAIL", EMAIL_HOST_USER or "")
DEFAULT_FROM_EMAIL = env.str("DEFAULT_FROM_EMAIL", EMAIL_HOST_USER or "")

# Admins
ADMINS = [
    (
        env.str("DJANGO_SUPERUSER_USERNAME", "admin"), 
        env.str("DJANGO_SUPERUSER_EMAIL", "admin@example.com")
    )
]

# Logging
LOGGING = LOGGING

# Security defaults (can be toggled by env in prod/dev)
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", False)
SESSION_COOKIE_SECURE = env.bool("SESSION_COOKIE_SECURE", False)
CSRF_COOKIE_SECURE = env.bool("CSRF_COOKIE_SECURE", False)
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", 0)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", False)
SECURE_HSTS_PRELOAD = env.bool("SECURE_HSTS_PRELOAD", False)

# Proxy headers
SECURE_PROXY_SSL_HEADER = None
USE_X_FORWARDED_HOST = False
USE_X_FORWARDED_PORT = False
