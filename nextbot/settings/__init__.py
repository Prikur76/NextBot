"""Select settings module depending on DJANGO_ENV or DJANGO_SETTINGS_MODULE.


By default, if DJANGO_SETTINGS_MODULE is set explicitly, Django will use it.
This file allows using DJANGO_ENV (dev|prod) as a convenient selector.
"""
import os


DJANGO_ENV = os.getenv("DJANGO_ENV")


if DJANGO_ENV == "prod":
    # explicit short name
    default = "nextbot.settings.prod"
else:
    default = "nextbot.settings.dev"


# If DJANGO_SETTINGS_MODULE already set externally, don't override it
if not os.getenv("DJANGO_SETTINGS_MODULE"):
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", default)


# Nothing else should live here — keep package import-safe.