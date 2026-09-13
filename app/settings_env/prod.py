"""Producao: debug sempre desligado e cookies endurecidos."""

import logging

from app.settings_env.base import *  # noqa: F403
from app.settings_env.base import env

DEBUG = False  # nunca por variavel de ambiente em producao

_log = logging.getLogger(__name__)
if not env("DJANGO_SECRET_KEY", default=""):
    _log.warning(
        "DJANGO_SECRET_KEY ausente: usando chave insegura de fallback. "
        "Defina DJANGO_SECRET_KEY no .env (ver docs/OPERACAO.md)."
    )

# Atras do Traefik (TLS termina nele).
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SECURE_HSTS_SECONDS = env.int("DJANGO_HSTS_SECONDS", default=0)  # ligar apos validar
