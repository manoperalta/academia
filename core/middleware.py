"""Middleware que instala o contexto de rede/unidade na requisicao."""

from __future__ import annotations

import logging

from django.http import HttpResponseForbidden

from core.context import limpar_contexto
from core.papeis import StatusRede
from core.tenancy import definir_contexto_da_requisicao

logger = logging.getLogger("core")


class RedeMiddleware:
    """Resolve a rede da requisicao, instala o contexto e aplica o bloqueio por status.

    Precisa vir depois de ``AuthenticationMiddleware`` (usa ``request.user``).
    """

    #: Caminhos que nunca dependem de rede (saude, estaticos, webhooks da plataforma).
    isolados = (
        "/static/",
        "/media/",
        "/admin/jsi18n/",
        "/api/v1/estado/",
    )

    #: Quando a rede esta bloqueada, ainda permitimos: login, admin, fatura, API e estaticos.
    permitidos_bloqueado = (
        "/accounts/",
        "/admin/",
        "/api/",
        "/static/",
        "/media/",
        "/meu-plano",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith(self.isolados):
            return self.get_response(request)

        try:
            definir_contexto_da_requisicao(request)
        except Exception:  # pragma: no cover - nunca derruba a requisicao por contexto
            logger.exception("Falha ao resolver o contexto de rede")
            limpar_contexto()
            return self.get_response(request)

        try:
            resposta = self._bloqueio_por_status(request)
            if resposta is not None:
                return resposta
            return self.get_response(request)
        finally:
            limpar_contexto()

    def _bloqueio_por_status(self, request):
        rede = getattr(request, "rede", None)
        if rede is None or rede.esta_ativa or rede.status == StatusRede.INADIMPLENTE:
            return None
        if request.path.startswith(self.permitidos_bloqueado):
            return None
        if (
            request.method in {"GET", "HEAD", "OPTIONS"}
            and rede.status == StatusRede.SOMENTE_LEITURA
        ):
            return None
        if not getattr(request.user, "is_authenticated", False):
            return None
        if getattr(request.user, "is_superuser", False):
            return None
        logger.warning("Escrita bloqueada na rede %s (status=%s)", rede.slug, rede.status)
        return HttpResponseForbidden(
            "A conta desta academia esta com o acesso bloqueado. "
            "Regularize o pagamento para voltar a editar os dados."
        )
