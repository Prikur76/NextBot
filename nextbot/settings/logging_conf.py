"""
Central logging configuration for Django project.

This file is imported inside base.py:
    from .logging_conf import LOGGING
"""
from pathlib import Path


# Directory for storing log files
BASE_DIR = Path(__file__).resolve().parents[2]
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)


LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,

    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} [{name}:{lineno}] {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname}: {message}",
            "style": "{",
        },
    },

    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },

        "file_general": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOG_DIR / "project.log"),
            "maxBytes": 10 * 1024 * 1024,  # 10 MB
            "backupCount": 5,
            "formatter": "verbose",
            "level": "INFO",
            "encoding": "utf-8",
            "delay": True,
        },

        "file_errors": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOG_DIR / "errors.log"),
            "maxBytes": 10 * 1024 * 1024,  # 10 MB
            "backupCount": 30,
            "formatter": "verbose",
            "level": "ERROR",
            "encoding": "utf-8",
        },

        "file_sql": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOG_DIR / "sql.log"),
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 3,
            "formatter": "verbose",
            "level": "DEBUG",
            "encoding": "utf-8",
            "delay": True,
        },

        "mail_admins": {
            "class": "django.utils.log.AdminEmailHandler",
            "level": "ERROR",
            "formatter": "verbose",
        },
    },

    "root": {
        "handlers": ["console", "file_general", "file_errors"],
        "level": "INFO",
    },

    "loggers": {
        "django": {
            "handlers": ["console", "file_general"],
            "level": "INFO",
            "propagate": False,
        },

        "django.security": {
            "handlers": ["file_errors"],
            "level": "WARNING",
            "propagate": False,
        },

        "django.request": {
            "handlers": ["file_errors", "mail_admins"],
            "level": "ERROR",
            "propagate": False,
        },

        "django.db.backends": {
            "handlers": ["file_sql"],
            "level": "INFO",
            "propagate": False,
        },

        # App-specific loggers
        "core.bot": {
            "handlers": ["console", "file_general"],
            "level": "INFO",
            "propagate": False,
        },

        "nextbot.custom": {
            "handlers": ["console", "file_errors"],
            "level": "WARNING",
            "propagate": False,
        },

        "core.clients": {
            "handlers": ["console", "file_general"],
            "level": "INFO",
            "propagate": False,
        },
        
        # Подавление подробных логов httpx
        "httpx": {
            "handlers": ["file_errors"],  # Только ошибки попадут в errors.log
            "level": "WARNING",           # Игнорируем INFO (POST, GET и т.п.)
            "propagate": False,
        },

        # Опционально: если используете httpcore (нижний уровень httpx)
        "httpcore": {
            "handlers": [],
            "level": "WARNING",
            "propagate": False,
        },

        # Опционально: подавить логи urllib3 (если используется requests)
        "urllib3": {
            "handlers": [],
            "level": "WARNING",
            "propagate": False,
        },
    },
}
