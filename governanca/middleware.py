"""Middlewares de governanca: 2FA obrigatorio, metricas por cliente e log com contexto."""
from __future__ import annotations

import logging
import time

from django.shortcuts import redirect
from django.urls import reverse

from core.seguranca import (
    dois_fatores_ativo, exigir_2fa_para, sessao_verificada,
)

logger = logging.getLogger("governanca")

#: rotas que nunca passam pelo desafio de 2FA (login, arquivos e a propria pagina do fator)
CAMINHOS_LIVRES = (
    "/entrar/", "/2fa/", "/status/", "/midia/", "/static/", "/media/", "/api/", "/admin/",
    "/.well-known/",
)


class DoisFatoresMiddleware:
    """Cobra o segundo fator de quem ja ativou -- e obriga a equipe da plataforma (RNF-009)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        usuario = getattr(request, "user", None)
        caminho = request.path or "/"

        if usuario is None or not getattr(usuario, "is_authenticated", False):
            return self.get_response(request)
        if caminho.startswith(CAMINHOS_LIVRES) or request.path_info.startswith("/2fa/"):
            return self.get_response(request)
        # A equipe da plataforma precisa ter o fator ativo (RNF-009) -- vale antes de tudo.
        if exigir_2fa_para(usuario) and not dois_fatores_ativo(usuario):
            return redirect(f"{reverse('governanca:dois_fatores_cadastrar')}?obrigatorio=1")
        if dois_fatores_ativo(usuario) and not sessao_verificada(request):
            return redirect(f"{reverse('governanca:dois_fatores')}?proximo={request.get_full_path()}")
        return self.get_response(request)


class MetricasMiddleware:
    """Mede tempo/status por cliente e guarda os erros 5xx (RNF-008)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        inicio = time.monotonic()
        resposta = self.get_response(request)
        duracao_ms = int((time.monotonic() - inicio) * 1000)
        try:
            from governanca.servicos import registrar_erro, registrar_requisicao

            rede = getattr(request, "rede", None)
            registrar_requisicao(rede, resposta.status_code, duracao_ms)
            if resposta.status_code >= 500:
                registrar_erro(
                    rede, request.path, request.method, resposta.status_code,
                    tipo="ErroInterno", mensagem="resposta 5xx",
                    usuario=getattr(request, "user", None),
                )
        except Exception as erro:  # noqa: BLE001 - observabilidade nunca derruba a resposta
            logger.debug("falha ao registrar metrica: %s", erro)
        return resposta

    def process_exception(self, request, excecao):
        """Registra a excecao com o cliente e um trecho de traceback (RNF-008)."""
        import traceback

        try:
            from governanca.servicos import registrar_erro

            registrar_erro(
                getattr(request, "rede", None), request.path, request.method, 500,
                tipo=type(excecao).__name__, mensagem=str(excecao),
                traceback_curto="".join(traceback.format_exception(excecao))[-4000:],
                usuario=getattr(request, "user", None),
            )
        except Exception:  # noqa: BLE001
            pass
        return None


class FiltroDeContextoDeLog(logging.Filter):
    """Coloca tenant_id e usuario em cada linha de log (RNF-008)."""

    def filter(self, record) -> bool:
        try:
            from core.context import rede_atual, usuario_atual

            rede = rede_atual()
            usuario = usuario_atual()
            record.tenant_id = getattr(rede, "pk", None) or "-"
            record.tenant = getattr(rede, "slug", None) or "-"
            record.usuario = getattr(usuario, "username", None) or "-"
        except Exception:  # noqa: BLE001
            record.tenant_id, record.tenant, record.usuario = "-", "-", "-"
        return True
