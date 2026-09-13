"""Observabilidade por cliente: metricas, erros, alertas e log com contexto (RNF-008)."""
from __future__ import annotations

import logging

from django.urls import reverse

from governanca.models import ErroTenant, MetricaTenant
from governanca.servicos import (
    agregar_metricas, alertas_pendentes, registrar_erro, registrar_requisicao, resumo_de_saude,
)


def test_metricas_somam_requisicoes_erros_e_tempo(db, rede):
    registrar_requisicao(rede, 200, 100)
    registrar_requisicao(rede, 500, 300)
    assert agregar_metricas() >= 1
    metrica = MetricaTenant.objects.get(rede=rede)
    assert metrica.requisicoes == 2
    assert metrica.erros_5xx == 1
    assert metrica.erros_4xx == 0
    assert metrica.tempo_max_ms == 300
    assert metrica.tempo_medio_ms == 200


def test_erro_repetido_nao_inunda_a_lista(db, rede):
    registrar_erro(rede, "/gestao/alunos/", "GET", 500, tipo="ValueError", mensagem="quebrou")
    registrar_erro(rede, "/gestao/alunos/", "GET", 500, tipo="ValueError", mensagem="quebrou")
    assert ErroTenant.objects.filter(rede=rede).count() == 1


def test_resumo_de_saude_por_cliente(db, rede):
    registrar_requisicao(rede, 200, 50)
    agregar_metricas()
    registrar_erro(rede, "/x/", "GET", 500, tipo="ErroInterno")
    resumo = resumo_de_saude(horas=24)
    linha = next(item for item in resumo["linhas"] if item["rede"] == rede)
    assert linha["requisicoes"] == 1
    assert linha["ultimo_erro"] is not None


def test_alerta_quando_ha_muitos_5xx(db, rede):
    for _ in range(6):
        registrar_requisicao(rede, 500, 80)
    agregar_metricas()
    assert any("erros 5xx" in alerta for alerta in alertas_pendentes())


def test_middleware_mede_a_requisicao(cliente_governanca, rede):
    cliente_governanca.get(reverse("gestao:visao_geral"))
    assert agregar_metricas() >= 1
    metrica = MetricaTenant.objects.filter(rede=rede).first()
    assert metrica is not None and metrica.requisicoes >= 1


def test_filtro_de_log_poe_tenant_e_usuario(db, rede, usuario_governanca):
    from core.context import definir_contexto, limpar_contexto
    from governanca.middleware import FiltroDeContextoDeLog

    definir_contexto(rede=rede, usuario=usuario_governanca)
    registro = logging.LogRecord("teste", logging.INFO, __file__, 1, "mensagem", None, None)
    assert FiltroDeContextoDeLog().filter(registro) is True
    assert registro.tenant == rede.slug
    assert registro.usuario == usuario_governanca.username
    limpar_contexto()

    sem_contexto = logging.LogRecord("teste", logging.INFO, __file__, 1, "mensagem", None, None)
    assert FiltroDeContextoDeLog().filter(sem_contexto) is True
    assert sem_contexto.tenant_id == "-"


def test_pagina_de_status_publica(client, db, rede):
    resposta = client.get(reverse("governanca:status"))
    assert resposta.status_code == 200
    conteudo = resposta.content.decode()
    assert "Backup do banco" in conteudo
