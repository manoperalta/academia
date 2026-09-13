"""URLconf da DEMONSTRACAO: as rotas do projeto mais os arquivos estaticos.

O uWSGI tira o `/demo` do caminho antes de chamar o Django (SCRIPT_NAME=/demo). Como o prefixo pode
chegar de duas formas dependendo do roteamento, os estaticos sao servidos nos dois formatos:
`/static/...` e `/demo/static/...`.

Tem um ultimo padrao que so serve para diagnostico: ele registra no log o caminho que chegou e
responde 404 explicando. Serve arquivo pelo Django de proposito: e demonstracao, sem nginx na frente.
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.http import HttpResponseNotFound
from django.urls import re_path
from django.views.static import serve

from app.urls import urlpatterns as rotas_do_projeto

logger = logging.getLogger("demonstracao")


def nao_encontrado(request, resto: str = ""):
    """Registra o caminho que chegou de verdade (ajuda a achar erro de prefixo)."""
    logger.warning(
        "caminho nao atendido: path=%s | path_info=%s | script_name=%s",
        request.path,
        request.path_info,
        request.META.get("SCRIPT_NAME", ""),
    )
    return HttpResponseNotFound(
        f"Sem rota para {request.path} (path_info={request.path_info})"
    )


urlpatterns = [
    *rotas_do_projeto,
    re_path(r"^static/(?P<path>.*)$", serve, {"document_root": settings.STATIC_ROOT}),
    re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}),
    re_path(r"^demo/static/(?P<path>.*)$", serve, {"document_root": settings.STATIC_ROOT}),
    re_path(r"^demo/media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}),
    re_path(r"^(?P<resto>.*)$", nao_encontrado),
]
