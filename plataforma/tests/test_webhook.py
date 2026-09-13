"""Webhook do gateway: token, idempotencia e efeitos."""
from __future__ import annotations

import json

import pytest
from django.urls import reverse

from plataforma.models import ConfiguracaoPlataforma, EventoGateway, StatusFatura
from plataforma.servicos import emitir_cobranca_da_fatura, gerar_fatura

URL = "/plataforma/webhook/asaas/"


def _payload(fatura, identificador_evento="evt-1", status="RECEIVED"):
    return {
        "id": identificador_evento,
        "event": "PAYMENT_RECEIVED",
        "payment": {"id": fatura.gateway_id or f"sim-{fatura.numero}", "status": status,
                    "value": 150.0},
    }


def _enviar(client, payload, token=None):
    cabecalhos = {"asaas-access-token": token} if token else {}
    return client.post(URL, data=json.dumps(payload), content_type="application/json",
                       headers=cabecalhos)


def test_webhook_da_baixa_e_e_idempotente(db, client, rede, assinatura):
    fatura = emitir_cobranca_da_fatura(gerar_fatura(assinatura))
    primeira = _enviar(client, _payload(fatura))
    assert primeira.status_code == 200
    assert primeira.json()["processado"] is True
    fatura.refresh_from_db()
    assert fatura.status == StatusFatura.PAGA

    repetida = _enviar(client, _payload(fatura))
    assert repetida.status_code == 200
    assert repetida.json()["processado"] is False
    assert EventoGateway.objects.count() == 1


def test_webhook_exige_token_quando_configurado(db, client, rede, assinatura):
    configuracao = ConfiguracaoPlataforma.obter()
    configuracao.token_webhook = "segredo-do-webhook"
    configuracao.save()
    fatura = emitir_cobranca_da_fatura(gerar_fatura(assinatura))
    assert _enviar(client, _payload(fatura)).status_code == 403
    assert _enviar(client, _payload(fatura), token="errado").status_code == 403
    assert _enviar(client, _payload(fatura), token="segredo-do-webhook").status_code == 200


def test_webhook_sem_id_de_evento_e_recusado(db, client):
    resposta = client.post(URL, data=json.dumps({"event": "PAYMENT_RECEIVED"}),
                           content_type="application/json")
    assert resposta.status_code == 400


def test_webhook_com_payload_invalido(db, client):
    resposta = client.post(URL, data="{isso nao e json", content_type="application/json")
    assert resposta.status_code == 400


def test_webhook_de_fatura_desconhecida_nao_quebra(db, client):
    resposta = _enviar(client, {"id": "evt-orfao", "payment": {"id": "nao-existe",
                                                              "status": "RECEIVED"}})
    assert resposta.status_code == 200
    evento = EventoGateway.objects.get(evento_id="evt-orfao")
    assert "nao encontrada" in evento.resultado


def test_webhook_de_estorno_marca_fatura(db, client, rede, assinatura):
    fatura = emitir_cobranca_da_fatura(gerar_fatura(assinatura))
    fatura.marcar_paga()
    resposta = _enviar(client, _payload(fatura, "evt-estorno", status="REFUNDED"))
    assert resposta.status_code == 200
    fatura.refresh_from_db()
    assert fatura.status == StatusFatura.ESTORNADA
