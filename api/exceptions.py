"""Erros no padrao RFC 7807 (``application/problem+json``) com codigo de negocio."""

from __future__ import annotations

import logging
from typing import Any

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler as handler_padrao

logger = logging.getLogger("api")

#: Codigos estaveis de negocio (o agente decide o que fazer com isso).
CODIGO_LIMITE = "limite_pacote_atingido"
CODIGO_BLOQUEIO = "academia_bloqueada"
CODIGO_ESCOPO = "escopo_insuficiente"
CODIGO_VALIDACAO = "dados_invalidos"


class ErroDeNegocio(exceptions.APIException):
    """Erro previsto de regra de negocio (vira 409/422 com codigo estavel)."""

    status_code = status.HTTP_409_CONFLICT
    default_detail = "Operacao nao permitida pelas regras de negocio."
    codigo = "regra_de_negocio"

    def __init__(self, detail=None, codigo=None, status_code=None, extra=None):
        self.codigo = codigo or self.codigo
        self.extra = extra or {}
        if status_code:
            self.status_code = status_code
        super().__init__(detail or self.default_detail)


class LimiteDoPacote(ErroDeNegocio):
    """Bater no limite do pacote e erro de negocio previsivel, nao 500."""

    codigo = CODIGO_LIMITE
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Limite do pacote atingido."


def _problem(status_code: int, titulo: str, detalhe: str, codigo: str, extra: dict | None = None):
    corpo: dict[str, Any] = {
        "type": f"https://academia.safestack.com.br/erros/{codigo}",
        "title": titulo,
        "status": status_code,
        "detail": detalhe,
        "codigo": codigo,
    }
    if extra:
        corpo.update(extra)
    return Response(corpo, status=status_code, content_type="application/problem+json")


def tratar_excecao(exc, context):
    """Substitui o handler padrao do DRF pelo formato problem+json."""
    resposta = handler_padrao(exc, context)
    if resposta is None:
        return None

    status_code = resposta.status_code
    detalhe = resposta.data
    extra = {}
    codigo = "erro"

    if isinstance(exc, ErroDeNegocio):
        codigo = exc.codigo
        detalhe = str(exc.detail)
        extra = exc.extra
    elif isinstance(exc, exceptions.ValidationError):
        codigo = CODIGO_VALIDACAO
        extra = {"errors": detalhe}
        detalhe = "Um ou mais campos estao invalidos."
    elif isinstance(exc, DjangoValidationError):
        codigo = CODIGO_VALIDACAO
        extra = {"errors": exc.messages}
        detalhe = "Um ou mais campos estao invalidos."
    elif isinstance(exc, (exceptions.NotAuthenticated, exceptions.AuthenticationFailed)):
        codigo = "nao_autenticado"
        detalhe = "Credencial ausente, invalida ou expirada."
    elif isinstance(exc, (exceptions.PermissionDenied, DjangoPermissionDenied)):
        codigo = CODIGO_ESCOPO
        detalhe = str(getattr(exc, "detail", "Permissao insuficiente."))
    elif isinstance(exc, Http404):
        codigo = "nao_encontrado"
        detalhe = "Recurso nao encontrado nesta academia."
    elif status_code >= 500:
        codigo = "erro_interno"
        logger.exception("Erro nao tratado na API", exc_info=exc)
        detalhe = "Erro interno. Informe o request_id ao suporte."

    titulo = {
        400: "Dados invalidos",
        401: "Nao autenticado",
        403: "Acesso negado",
        404: "Nao encontrado",
        405: "Metodo nao permitido",
        409: "Conflito de regra de negocio",
        429: "Limite de requisicoes",
    }.get(status_code, "Erro")

    return _problem(status_code, titulo, str(detalhe), codigo, extra)
