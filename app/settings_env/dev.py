"""Desenvolvimento: conveniencia acima de rigor, sem segredo real."""

from app.settings_env.base import *  # noqa: F403
from app.settings_env.base import env

DEBUG = env.bool("DJANGO_DEBUG", default=True)
ALLOWED_HOSTS = env.list(
    "DJANGO_ALLOWED_HOSTS",
    default=["localhost", "127.0.0.1", "0.0.0.0", "testserver", "*"],
)
DEBUG_TOKEN = env("DJANGO_DEBUG_TOKEN", default="dev")

INTERNAL_IPS = ["127.0.0.1"]

# E-mail sempre no console em desenvolvimento (nao dispara para aluno de verdade).
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

if env.bool("DJANGO_SQL_ECHO", default=False):
    LOGGING["loggers"]["django.db.backends"] = {  # noqa: F405
        "handlers": ["console"],
        "level": "DEBUG",
        "propagate": False,
    }
