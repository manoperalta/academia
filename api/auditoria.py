"""Helper de auditoria: um lugar so para registrar o que importa."""

from __future__ import annotations

import logging

from django.db import DatabaseError

from api.models import RegistroAuditoria
from core.context import rede_atual, unidade_atual, usuario_atual

logger = logging.getLogger("api")


def registrar(
    acao: str,
    entidade: str,
    *,
    entidade_id="",
    descricao: str = "",
    dados_antes=None,
    dados_depois=None,
    request=None,
    token=None,
    pedido_origem: str = "",
) -> RegistroAuditoria | None:
    """Grava um evento de auditoria. Nunca derruba a operacao principal."""
    ip = None
    request_id = ""
    usuario = usuario_atual()
    rede = rede_atual()
    unidade = unidade_atual()
    if request is not None:
        ip = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip() or request.META.get(
            "REMOTE_ADDR"
        )
        request_id = getattr(request, "request_id", "") or request.META.get("HTTP_X_REQUEST_ID", "")
        usuario = getattr(request, "user", None) or usuario
        rede = getattr(request, "rede", None) or rede
        unidade = getattr(request, "unidade", None) or unidade
    if token is None and request is not None:
        token = getattr(request, "token_servico", None)
    if token is not None:
        rede = token.rede
        unidade = token.unidade
        usuario = None
    try:
        # Identidade de servico (token) nao e um usuario real: fica no campo ``token``.
        if usuario is not None and not getattr(usuario, "pk", None):
            usuario = None
        return RegistroAuditoria.objects.create(
            rede=rede,
            unidade=unidade,
            usuario=usuario,
            token=token,
            acao=acao,
            entidade=entidade,
            entidade_id=str(entidade_id or ""),
            descricao=descricao[:255],
            dados_antes=dados_antes,
            dados_depois=dados_depois,
            pedido_origem=pedido_origem,
            ip=ip,
            request_id=request_id,
        )
    except DatabaseError:  # pragma: no cover - auditoria nao pode quebrar o fluxo
        logger.exception("Falha ao gravar auditoria de %s", entidade)
        return None
