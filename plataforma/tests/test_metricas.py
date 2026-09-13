"""Metricas da plataforma: MRR, ARR, churn, ticket medio e distribuicao."""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from plataforma.models import Assinatura, StatusFatura
from plataforma.servicos import gerar_fatura, metricas
from plataforma.tests.conftest import criar_assinatura, criar_pacote


def test_mrr_normaliza_ciclo_anual(db, rede, outra_rede, pacote_prata, pacote_ouro):
    criar_assinatura(rede, pacote_prata, ciclo="mensal")
    criar_assinatura(outra_rede, pacote_ouro, ciclo="anual")
    dados = metricas()
    assert dados["mrr"] == Decimal("650.00")
    assert dados["arr"] == Decimal("7800.00")
    assert dados["tenants_ativos"] == 2
    assert dados["ticket_medio"] == Decimal("325.00")
    assert {item["pacote"] for item in dados["por_pacote"]} == {"Prata", "Ouro"}


def test_trial_conta_separado(db, rede, pacote_ouro):
    criar_assinatura(rede, pacote_ouro, dias=10, trial=True)
    dados = metricas()
    assert dados["tenants_trial"] == 1


def test_churn_do_mes(db, rede, outra_rede, pacote_prata):
    criar_assinatura(rede, pacote_prata)
    cancelada = criar_assinatura(outra_rede, pacote_prata)
    cancelada.cancelada_em = timezone.localdate()
    cancelada.save()
    dados = metricas()
    assert dados["churn_mes"] == 1
    assert dados["churn_percentual"] == 50.0
    assert dados["tenants_ativos"] == 1


def test_inadimplencia_e_em_aberto(db, rede, assinatura):
    hoje = timezone.localdate()
    fatura = gerar_fatura(assinatura)
    fatura.vencimento = hoje - timedelta(days=2)
    fatura.save()
    dados = metricas()
    assert dados["tenants_inadimplentes"] == 1
    assert dados["em_aberto"] == Decimal("150.00")


def test_recebido_no_mes(db, rede, assinatura):
    fatura = gerar_fatura(assinatura)
    fatura.marcar_paga()
    dados = metricas()
    assert dados["recebido_mes"] == Decimal("150.00")


def test_novos_tenants_no_mes(db, rede):
    assert metricas()["novos_tenants_mes"] >= 1
