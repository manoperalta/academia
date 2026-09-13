"""Ambiente de DEMONSTRACAO, publicado em academia.safestack.com.br/demo/.

Por que existe: a demonstracao roda no mesmo dominio da producao, num caminho (`/demo/`), com banco
proprio e cookie proprio. Nada aqui toca a producao: e outro container, outro banco e outro prefixo.

O prefixo vem de FORCE_SCRIPT_NAME, o que faz o Django gerar todas as URLs ja com `/demo` -- por isso
nao ha nenhum patch de template ou de view apontando para o demo.
"""

from app.settings_env.base import *  # noqa: F403
from app.settings_env.base import env  # noqa: E402

# Prefixo do demonstracao: tudo que o Django gerar sai com /demo na frente.
FORCE_SCRIPT_NAME = "/demo"

DEBUG = env.bool("DJANGO_DEBUG", default=True)

ALLOWED_HOSTS = [
    "academia.safestack.com.br",
    "localhost",
    "127.0.0.1",
    "testserver",
    "[::1]",
]

CSRF_TRUSTED_ORIGINS = [
    "https://academia.safestack.com.br",
    "http://localhost:8004",
    "http://127.0.0.1:8004",
]

# Estaticos e midia com o prefixo, servidos pelo proprio Django (demonstracao, nao producao).
STATIC_URL = "/demo/static/"
MEDIA_URL = "/demo/media/"
STATIC_ROOT = env.str("DJANGO_STATIC_ROOT", default="/app/staticfiles")

# Cookie isolado do demo: entrar no demo nao derruba nem substitui a sessao da producao.
SESSION_COOKIE_PATH = "/demo"
CSRF_COOKIE_PATH = "/demo"
SESSION_COOKIE_NAME = "sessionid_demo"
CSRF_COOKIE_NAME = "csrftoken_demo"

# Demonstracao: e-mail e WhatsApp na tela, sem chamar provedor de verdade.
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Sem o desafio de 2FA: e uma demonstracao de clique, com dado de mentira e banco separado. A
# producao mantem o middleware -- o que muda aqui e so esta lista.
MIDDLEWARE = [item for item in MIDDLEWARE if "DoisFatoresMiddleware" not in item]  # noqa: F405

# Demonstracao: sem cobranca de 2FA tambem para a equipe da plataforma (RNF-009 fica na producao).
EXIGIR_2FA_PLATAFORMA = False
