"""Faturas, emissao de cobranca e regua de cobranca (idempotente)."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from core.papeis import StatusRede
from plataforma.models import (
    EventoCobranca,
    MarcoRegua,
    StatusFatura,
)
from plataforma.servicos import (
    aplicar_regua,
    emitir_cobranca_da_fatura,
    gerar_fatura,
    gerar_faturas_do_dia,
    processar_evento_gateway,
)
from plataforma.tests.conftest import criar_assinatura


def test_gerar_fatura_calcula_valor_e_numero(db, rede, assinatura):
    fatura = gerar_fatura(assinatura)
    assert fatura.numero.startswith("FAT-")
    assert fatura.valor_final == Decimal("150.00")
    assert fatura.status == StatusFatura.ABERTA
    assert fatura.em_aberto is True


def test_gerar_fatura_e_idempotente_por_periodo(db, rede, assinatura):
    gerar_fatura(assinatura)
    assert gerar_fatura(assinatura) is None


def test_desconto_da_assinatura_entra_no_valor(db, rede, assinatura):
    assinatura.desconto_percentual = Decimal("10")
    assinatura.save()
    assert assinatura.valor_do_ciclo() == Decimal("135.00")


def test_gerar_faturas_do_dia_avanca_o_ciclo_e_emite_cobranca(db, rede, assinatura):
    hoje = timezone.localdate()
    assinatura.renovacao_em = hoje
    assinatura.save()
    geradas = gerar_faturas_do_dia(hoje)
    assert len(geradas) == 1
    fatura = geradas[0]
    assert fatura.gateway == "simulado"
    assert fatura.pix_copia_cola.startswith("00020126")
    assinatura.refresh_from_db()
    assert assinatura.renovacao_em == hoje + timedelta(days=30)


def test_emissao_guarda_dados_do_gateway(db, rede, assinatura):
    fatura = emitir_cobranca_da_fatura(gerar_fatura(assinatura))
    assert fatura.gateway_id == f"sim-{fatura.numero}"
    assert fatura.link_pagamento


def test_regua_dispara_cada_marco_uma_unica_vez(db, rede, assinatura):
    hoje = timezone.localdate()
    fatura = gerar_fatura(assinatura)
    fatura.vencimento = hoje - timedelta(days=1)
    fatura.save()
    primeiro = aplicar_regua(hoje)
    segundo = aplicar_regua(hoje)
    # quem ja passou de D0 e chegou em D+1 recebe os dois avisos (nao perder disparo)...
    assert primeiro["disparos"] == 2
    # ...mas nunca duas vezes o mesmo marco
    assert segundo["disparos"] == 0
    assert EventoCobranca.objects.filter(fatura=fatura, marco=MarcoRegua.D1).count() == 1
    fatura.refresh_from_db()
    assert fatura.status == StatusFatura.VENCIDA


def test_regua_bloqueia_em_d10_e_suspende_em_d30(db, rede, assinatura):
    hoje = timezone.localdate()
    fatura = gerar_fatura(assinatura)
    fatura.vencimento = hoje - timedelta(days=10)
    fatura.save()
    aplicar_regua(hoje)
    rede.refresh_from_db()
    assert rede.status == StatusRede.SOMENTE_LEITURA
    fatura.vencimento = hoje - timedelta(days=30)
    fatura.save()
    aplicar_regua(hoje)
    rede.refresh_from_db()
    assert rede.status == StatusRede.SUSPENSO


def test_regua_avisa_o_trial_e_bloqueia_no_fim(db, rede, pacote_ouro):
    hoje = timezone.localdate()
    assinatura = criar_assinatura(rede, pacote_ouro, dias=7, trial=True)
    rede.status = StatusRede.TRIAL
    rede.trial_termina_em = hoje + timedelta(days=7)
    rede.save()
    aplicar_regua(hoje)
    assert EventoCobranca.objects.filter(rede=rede, marco=MarcoRegua.TRIAL_7).exists()
    assinatura.trial_termina_em = hoje - timedelta(days=1)
    assinatura.save()
    aplicar_regua(hoje)
    rede.refresh_from_db()
    assert rede.status == StatusRede.SOMENTE_LEITURA


def test_pagamento_pelo_webhook_reativa_o_tenant(db, rede, assinatura):
    hoje = timezone.localdate()
    fatura = gerar_fatura(assinatura)
    fatura.vencimento = hoje - timedelta(days=30)
    fatura.save()
    aplicar_regua(hoje)
    rede.refresh_from_db()
    assert rede.status == StatusRede.SUSPENSO
    emitir_cobranca_da_fatura(fatura)
    processar_evento_gateway(
        {
            "id": "evt-pagamento-1",
            "payment": {"id": fatura.gateway_id, "status": "RECEIVED", "value": 150.0},
        }
    )
    rede.refresh_from_db()
    fatura.refresh_from_db()
    assert rede.status == StatusRede.ATIVO
    assert fatura.status == StatusFatura.PAGA


def test_baixa_manual_e_idempotente(db, rede, assinatura):
    fatura = gerar_fatura(assinatura)
    assert fatura.marcar_paga() is True
    assert fatura.marcar_paga() is False


def test_dias_de_atraso(db, rede, assinatura):
    hoje = timezone.localdate()
    fatura = gerar_fatura(assinatura)
    fatura.vencimento = hoje - timedelta(days=5)
    fatura.save()
    assert fatura.dias_de_atraso == 5
    fatura.marcar_paga()
    assert fatura.dias_de_atraso == 0
