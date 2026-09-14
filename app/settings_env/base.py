"""
Configuracao comum a todos os ambientes.

Regra do projeto: nenhum segredo no codigo e nenhuma diferenca de comportamento
escondida. O que muda por ambiente fica em ``dev.py``/``prod.py``/``test.py``.
"""

import os
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
    DJANGO_CSRF_TRUSTED_ORIGINS=(list, []),
    DJANGO_EMAIL_BACKEND=(str, "django.core.mail.backends.console.EmailBackend"),
)

# Le .env quando existir (docker-compose tambem injeta por env_file).
environ.Env.read_env(BASE_DIR / ".env")

# --- Seguranca -------------------------------------------------------------
SECRET_KEY = env("DJANGO_SECRET_KEY", default="django-insecure-dev-nao-usar-em-producao")
DEBUG = env("DJANGO_DEBUG")
DEBUG_TOKEN = env("DJANGO_DEBUG_TOKEN", default="")
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env("DJANGO_CSRF_TRUSTED_ORIGINS")
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# --- Aplicacoes ------------------------------------------------------------
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

TERCEIROS = [
    "rest_framework",
    "django_filters",
    "drf_spectacular",
]

LOCAIS = [
    "core",
    "rede",
    "remuneracao",
    "gamificacao",
    "nps",
    "area_do_aluno",
    "governanca",
    "vitrine",
    "plataforma",
    "gestao",
    "api",
    "usuarios",
    "professores",
    "academia",
    "dashboard",
    "accounts",
    "aulas",
    "agendamento",
    "painel",
    "financeiro",
    "relatorios",
    "notificacoes",
    "documentos",
    "conta",
    "portal_do_aluno",
    "painel_do_professor",
    "treinos",
    "design",
    "pdv",
    "fiscal",
    "cobranca",
    "acesso",
    "busca",
    "relacionamento",
    "midia",
    "integracoes",
]

INSTALLED_APPS = DJANGO_APPS + TERCEIROS + LOCAIS

# --- Middleware ------------------------------------------------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "core.middleware.RedeMiddleware",
    "app.middleware_debug.DebugLocalAutorizadoMiddleware",
    "governanca.middleware.DoisFatoresMiddleware",
    "governanca.middleware.MetricasMiddleware",
]

ROOT_URLCONF = "app.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "academia.context_processors.site_config",
                "core.context_processors.contexto_rede",
                "gestao.context_processors.menu_do_painel",
            ],
        },
    },
]

WSGI_APPLICATION = "app.wsgi.application"

# --- Banco de dados --------------------------------------------------------
# DATABASE_URL tem precedencia (12-factor); sem ela, SQLite local.
DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
    )
}
DATABASES["default"]["ATOMIC_REQUESTS"] = False
DATABASES["default"].setdefault("OPTIONS", {})

# --- Autenticacao ----------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
AUTH_USER_MODEL = "accounts.CustomUser"
LOGIN_REDIRECT_URL = "acesso:entrada"
LOGOUT_REDIRECT_URL = "login"

# --- Internacionalizacao ---------------------------------------------------
LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

# --- Arquivos estaticos e midia -------------------------------------------
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/midia/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- E-mail ----------------------------------------------------------------
EMAIL_BACKEND = env("DJANGO_EMAIL_BACKEND")
EMAIL_HOST = env("DJANGO_EMAIL_HOST", default="")
EMAIL_PORT = env.int("DJANGO_EMAIL_PORT", default=587)
EMAIL_USE_TLS = env.bool("DJANGO_EMAIL_USE_TLS", default=True)
EMAIL_HOST_USER = env("DJANGO_EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("DJANGO_EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = env("DJANGO_DEFAULT_FROM_EMAIL", default="noreply@academia.com")

# --- DRF / API -------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "api.authentication.TokenServicoAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "api.pagination.PaginacaoPadrao",
    "PAGE_SIZE": 25,
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.ScopedRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "token": "600/min",
        "usuario": "120/min",
        "anônimo": "30/min",
    },
    "EXCEPTION_HANDLER": "api.exceptions.tratar_excecao",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DATETIME_FORMAT": "%Y-%m-%dT%H:%M:%S%z",
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Academia System API",
    "DESCRIPTION": (
        "API REST para administracao remota das redes de academias. "
        "Escopos por recurso e recorte de rede/unidade."
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SORT_OPERATIONS": False,
}

# --- Logging ---------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "padrao": {
            "format": "[{asctime}] {levelname} {name} rede={rede_id} user={usuario} {message}",
            "style": "{",
        },
    },
    "filters": {
        "rede": {"()": "core.logging_filters.FiltroRede"},
        "contexto": {"()": "governanca.middleware.FiltroDeContextoDeLog"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "padrao",
            "filters": ["rede", "contexto"],
        },
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django.request": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "api": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "core": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}

# Pasta dos backups do banco e das exportacoes por cliente (RNF-005)
BACKUP_DIR = BASE_DIR / "backups"

# ------------------------------------------------ API v1 (fase 7)
API_JWT_SECRET = os.environ.get("API_JWT_SECRET", "")
API_JWT_VALIDADE = 3600
#: Onde as tarefas assincronas gravam o CSV do relatorio. Dentro de MEDIA_ROOT: artefato de
#: execucao nao pode cair no diretorio do codigo (o caminho relativo sujava a arvore).
TAREFAS_DIR = os.environ.get("TAREFAS_DIR", MEDIA_ROOT / "tarefas")
