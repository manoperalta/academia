import os

os.environ.setdefault("DJANGO_ENV", "test")

"""Testes: rapido e deterministico (nao use isto em producao)."""

from app.settings_env.base import *  # noqa: F401,F403
from app.settings_env.base import env

DEBUG = False
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1", "*"]
DEBUG_TOKEN = "teste"

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

# Barulho zero nos testes (ver docs/PLANO_TESTES.md).
LOGGING["root"]["level"] = "ERROR"  # noqa: F405
for _logger in LOGGING["loggers"].values():  # noqa: F405
    _logger["level"] = "ERROR"

DATABASES["default"]["TEST"] = {  # noqa: F405
    "NAME": env("DJANGO_TEST_DB_NAME", default=None),
}
