"""Webhooks de saida: assinatura HMAC, reentrega com backoff e log (RF-API-001/002/003)."""
from __future__ import annotations

import json
import secrets
import time
import urllib.error
import urllib.request
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from api.models import EntregaDeWebhook, WebhookDeSaida

#: Backoff das retentativas (RF-API-002): 1 min, 5 min, 30 min, 2 h, 12 h.
INTERVALOS = (60, 300, 1800, 7200, 43200)
TEMPO_LIMITE = 10

#: Eventos publicados (RF-API-001).
EVENTOS = {
    "aluno.criado", "aluno.inativado", "matricula.criada", "contrato.cancelado",
    "cobranca.gerada", "pagamento.confirmado", "pagamento.estornado", "checkin.realizado",
    "avaliacao.criada", "limite.pacote_atingido", "unidade.criada", "repasse.emitido",
    "fatura_plataforma.paga", "tenant.suspenso",
}


def _postar(url: str, corpo: bytes, cabecalhos: dict, timeout: int = TEMPO_LIMITE):
    requisicao = urllib.request.Request(url, data=corpo, headers=cabecalhos, method="POST")
    with urllib.request.urlopen(requisicao, timeout=timeout) as resposta:  # noqa: S310 - url do cliente
        return resposta.status, resposta.read()[:400].decode("utf-8", "replace")


def enfileirar_entrega(webhook: WebhookDeSaida, evento: str, payload: dict) -> EntregaDeWebhook:
    return EntregaDeWebhook.objects.create(
        webhook=webhook, evento=evento, entrega=secrets.token_hex(16), payload=payload,
    )


def disparar_evento(evento: str, payload: dict, rede=None) -> list[EntregaDeWebhook]:
    """Enfileira o evento para todos os webhooks ativos que o assinam (nao bloqueia o pedido)."""
    if evento not in EVENTOS:
        raise ValueError(f"evento desconhecido: {evento}")
    webhooks = WebhookDeSaida.objects.filter(estado=WebhookDeSaida.Estado.ATIVO).filter(
        Q(rede=rede) | Q(rede__isnull=True)
    )
    entregas = [enfileirar_entrega(webhook, evento, payload)
                for webhook in webhooks if webhook.escuta(evento)]
    return entregas


def entregar(entrega: EntregaDeWebhook, agora=None) -> EntregaDeWebhook:
    """Tenta uma entrega; em falha agenda a proxima tentativa com backoff."""
    agora = agora or timezone.now()
    webhook = entrega.webhook
    corpo = json.dumps({"evento": entrega.evento, "entrega": entrega.entrega,
                        "enviado_em": agora.isoformat(), "dados": entrega.payload},
                       ensure_ascii=False).encode("utf-8")
    momento = int(time.time())
    cabecalhos = {
        "Content-Type": "application/json",
        "X-Evento": entrega.evento,
        "X-Entrega": entrega.entrega,
        "X-Timestamp": str(momento),
        "X-Assinatura": f"sha256={webhook.assina(corpo, momento)}",
        "User-Agent": "academia-webhooks/1.0",
    }
    entrega.tentativas += 1
    try:
        codigo, texto = _postar(webhook.url, corpo, cabecalhos)
        if 200 <= codigo < 300:
            entrega.situacao = EntregaDeWebhook.Situacao.ENTREGUE
            entrega.entregue_em = agora
            entrega.resposta = f"{codigo} {texto[:120]}"
            entrega.proxima_tentativa = None
        else:
            entrega.situacao = EntregaDeWebhook.Situacao.FALHOU
            entrega.resposta = f"{codigo} {texto[:120]}"
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as erro:
        entrega.situacao = EntregaDeWebhook.Situacao.FALHOU
        entrega.resposta = str(erro)[:200]

    if entrega.situacao == EntregaDeWebhook.Situacao.FALHOU:
        if entrega.pode_retentar:
            espera = INTERVALOS[min(entrega.tentativas - 1, len(INTERVALOS) - 1)]
            entrega.proxima_tentativa = agora + timedelta(seconds=espera)
        else:
            entrega.situacao = EntregaDeWebhook.Situacao.DESISTIU
            entrega.proxima_tentativa = None
    entrega.save(update_fields=["tentativas", "situacao", "resposta", "proxima_tentativa",
                                "entregue_em"])
    return entrega


def entregar_pendentes(limite: int = 50, agora=None) -> dict:
    """Processa o que esta na hora: primeiro as entregas vencidas."""
    agora = agora or timezone.now()
    pendentes = EntregaDeWebhook.objects.select_related("webhook").filter(
        situacao__in=[EntregaDeWebhook.Situacao.PENDENTE, EntregaDeWebhook.Situacao.FALHOU],
    ).filter(Q(proxima_tentativa__isnull=True) | Q(proxima_tentativa__lte=agora))[:limite]
    entregues = falhas = 0
    for entrega in pendentes:
        entrega = entregar(entrega, agora=agora)
        if entrega.situacao == EntregaDeWebhook.Situacao.ENTREGUE:
            entregues += 1
        else:
            falhas += 1
    return {"processadas": entregues + falhas, "entregues": entregues, "falhas": falhas}


def reenviar(entrega: EntregaDeWebhook) -> EntregaDeWebhook:
    """Reenvio manual pela interface: zera a contagem e tenta de novo (RF-API-002)."""
    entrega.situacao = EntregaDeWebhook.Situacao.PENDENTE
    entrega.tentativas = 0
    entrega.proxima_tentativa = None
    entrega.save(update_fields=["situacao", "tentativas", "proxima_tentativa"])
    return entregar(entrega)
