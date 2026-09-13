"""
Seletor de configuracao por ambiente.

Mantem ``DJANGO_SETTINGS_MODULE=app.settings`` funcionando (compatibilidade com
o Docker/uWSGI atual) e escolhe o modulo real por ``DJANGO_ENV``:

    DJANGO_ENV=dev   -> desenvolvimento
    DJANGO_ENV=test  -> testes automatizados
    (padrao)         -> producao
"""

import os

AMBIENTE = os.environ.get("DJANGO_ENV", "prod")

if AMBIENTE == "dev":  # pragma: no cover - selecao de ambiente
    from app.settings_env.dev import *  # noqa: F403
elif AMBIENTE == "test":  # pragma: no cover
    from app.settings_env.test import *  # noqa: F403
else:  # pragma: no cover
    from app.settings_env.prod import *  # noqa: F403
