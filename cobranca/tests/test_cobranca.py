"""Testes da cobranca recorrente."""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from cobranca import servicos
from cobranca.models import AutorizacaoDeDebito, CobrancaRecorrente, EventoDaCobranca
from cobranca.servicos import ErroDeCobranca

pytestmark = pytest.mark.django_db


def autorizacao_ativa(aluno):
    autorizacao = servicos.autorizar_debito(aluno=aluno, chave_pix="aluno@pix.com")
    return servicos.ativar_autorizacao(autorizacao, "MAN-1")


def cobranca_do_mes(aluno) -> CobrancaRecorrente:
    servicos.gerar_cobrancas_do_mes(aluno.rede, timezone.localdate().replace(day=1))
    return CobrancaRecorrente.objects.get(aluno=aluno)


# ------------------------------------------------------------------ autorizacao


def test_autorizacao_exige_chave_pix_no_pix_automatico(aluno):
    with pytest.raises(ErroDeCobranca):
        servicos.autorizar_debito(aluno=aluno, chave_pix="  ")


def test_autorizacao_duplicada_e_recusada(aluno):
    servicos.autorizar_debito(aluno=aluno, chave_pix="a@pix.com")
    with pytest.raises(ErroDeCobranca):
        servicos.autorizar_debito(aluno=aluno, chave_pix="outra@pix.com")


def test_ativar_e_cancelar_autorizacao(aluno):
    autorizacao = autorizacao_ativa(aluno)
    assert autorizacao.situacao == AutorizacaoDeDebito.Situacao.ATIVA
    assert autorizacao.autorizada_em is not None
    servicos.cancelar_autorizacao(autorizacao)
    autorizacao.refresh_from_db()
    assert autorizacao.situacao == AutorizacaoDeDebito.Situacao.CANCELADA


def test_cancelar_autorizacao_cancela_cobrancas_em_aberto(aluno):
    autorizacao_ativa(aluno)
    cobranca = cobranca_do_mes(aluno)
    assert cobranca.situacao == CobrancaRecorrente.Situacao.PREVISTA
    servicos.cancelar_autorizacao(cobranca.autorizacao)
    cobranca.refresh_from_db()
    assert cobranca.situacao == CobrancaRecorrente.Situacao.CANCELADA


# ------------------------------------------------------------------ geracao do mes


def test_gerar_cobrancas_usa_o_valor_do_ultimo_pagamento(aluno):
    autorizacao_ativa(aluno)
    resultado = servicos.gerar_cobrancas_do_mes(aluno.rede, timezone.localdate().replace(day=1))
    assert len(resultado["criadas"]) == 1
    cobranca = CobrancaRecorrente.objects.get(aluno=aluno)
    assert cobranca.valor == Decimal("199.00")
    assert cobranca.vencimento.day == 10
    assert EventoDaCobranca.objects.filter(
        cobranca=cobranca, tipo=EventoDaCobranca.Tipo.CRIADA
    ).exists()


def test_gerar_cobrancas_e_idempotente(aluno):
    autorizacao_ativa(aluno)
    competencia = timezone.localdate().replace(day=1)
    servicos.gerar_cobrancas_do_mes(aluno.rede, competencia)
    segunda = servicos.gerar_cobrancas_do_mes(aluno.rede, competencia)
    assert segunda["criadas"] == []
    assert segunda["ja_existiam"] == ["Aluno Cobranca"]
    assert CobrancaRecorrente.objects.filter(aluno=aluno).count() == 1


def test_aluno_sem_autorizacao_nao_gera_cobranca(aluno):
    resultado = servicos.gerar_cobrancas_do_mes(aluno.rede, timezone.localdate().replace(day=1))
    assert resultado["criadas"] == []
    assert resultado["sem_autorizacao"] == ["Aluno Cobranca"]
    assert CobrancaRecorrente.objects.count() == 0


def test_simulacao_da_geracao_nao_grava(aluno):
    autorizacao_ativa(aluno)
    resultado = servicos.gerar_cobrancas_do_mes(
        aluno.rede, timezone.localdate().replace(day=1), dry_run=True
    )
    assert resultado["dry_run"] is True and len(resultado["criadas"]) == 1
    assert CobrancaRecorrente.objects.count() == 0


# ------------------------------------------------------------------ envio e retorno


def test_envio_simulado_marca_identificador_e_evento(aluno):
    autorizacao_ativa(aluno)
    cobranca = cobranca_do_mes(aluno)
    servicos.enviar_cobranca(cobranca)
    cobranca.refresh_from_db()
    assert cobranca.situacao == CobrancaRecorrente.Situacao.ENVIADA
    assert cobranca.identificador_no_banco.startswith("SIM-")
    assert cobranca.tentativas == 1
    assert EventoDaCobranca.objects.filter(
        cobranca=cobranca, tipo=EventoDaCobranca.Tipo.ENVIADA
    ).exists()


def test_envio_sem_autorizacao_ativa_e_recusado(aluno):
    autorizacao = servicos.autorizar_debito(aluno=aluno, chave_pix="a@pix.com")  # fica pendente
    competencia = timezone.localdate().replace(day=1)
    # cria a cobranca na mao, porque a geracao nao cria sem autorizacao ativa
    cobranca = CobrancaRecorrente.objects.create(
        rede=aluno.rede,
        unidade=aluno.unidade,
        aluno=aluno,
        autorizacao=autorizacao,
        competencia=competencia,
        valor=Decimal("199.00"),
        vencimento=competencia,
    )
    with pytest.raises(ErroDeCobranca):
        servicos.enviar_cobranca(cobranca)


def test_retorno_pago_registra_pagamento_e_nao_duplica(aluno, plano):
    from financeiro.models import Pagamento

    autorizacao_ativa(aluno)
    cobranca = cobranca_do_mes(aluno)
    servicos.enviar_cobranca(cobranca)
    primeiro = servicos.processar_retorno(cobranca, "pago", {"id": "PSP-1"})
    cobranca.refresh_from_db()
    assert primeiro["duplicado"] is False
    assert cobranca.situacao == CobrancaRecorrente.Situacao.PAGA
    assert cobranca.pagamento is not None
    assert Pagamento.objects.filter(pk=cobranca.pagamento_id, status="pago").exists()
    quantos = Pagamento.objects.filter(usuario=aluno.user).count()

    segundo = servicos.processar_retorno(cobranca, "pago", {"id": "PSP-1"})
    assert segundo["duplicado"] is True
    assert Pagamento.objects.filter(usuario=aluno.user).count() == quantos, "nao duplica pagamento"


def test_retorno_recusado_guarda_motivo(aluno):
    autorizacao_ativa(aluno)
    cobranca = cobranca_do_mes(aluno)
    servicos.enviar_cobranca(cobranca)
    servicos.processar_retorno(cobranca, "recusado", {}, motivo="saldo insuficiente")
    cobranca.refresh_from_db()
    assert cobranca.situacao == CobrancaRecorrente.Situacao.RECUSADA
    assert cobranca.motivo_da_recusa == "saldo insuficiente"


def test_retorno_devolvido_volta_para_recusada(aluno):
    autorizacao_ativa(aluno)
    cobranca = cobranca_do_mes(aluno)
    servicos.processar_retorno(cobranca, "devolvido", {})
    cobranca.refresh_from_db()
    assert cobranca.situacao == CobrancaRecorrente.Situacao.RECUSADA
    assert "devolvido" in cobranca.motivo_da_recusa


def test_retorno_desconhecido_e_recusado(aluno):
    autorizacao_ativa(aluno)
    cobranca = cobranca_do_mes(aluno)
    with pytest.raises(ErroDeCobranca):
        servicos.processar_retorno(cobranca, "inventado", {})


def test_retorno_em_lote_aplica_e_ignora_linhas_ruins(aluno):
    autorizacao_ativa(aluno)
    cobranca = cobranca_do_mes(aluno)
    conteudo = (
        f"cobranca,situacao,motivo\n{cobranca.pk},pago,\n999999,pago,\n{cobranca.pk},inventado,\n"
    )
    resultado = servicos.processar_retornos_em_lote(aluno.rede, conteudo)
    assert resultado["aplicados"] == 1
    assert resultado["ignorados"] == 2
    cobranca.refresh_from_db()
    assert cobranca.situacao == CobrancaRecorrente.Situacao.PAGA


# ------------------------------------------------------------------ regua e resumo


def test_fila_da_regua_traz_etapa_e_mensagem(aluno):
    autorizacao_ativa(aluno)
    cobranca = cobranca_do_mes(aluno)
    fila = servicos.fila_da_regua(aluno.rede)
    assert len(fila) == 1
    item = fila[0]
    assert item["cobranca"].pk == cobranca.pk
    assert item["mensagem"]


def test_resumo_da_cobranca_conta_e_soma(aluno, plano):
    autorizacao_ativa(aluno)
    cobranca = cobranca_do_mes(aluno)
    resumo = servicos.resumo_da_cobranca(aluno.rede)
    assert resumo["total"] == 1 and resumo["em_aberto"] == 1
    assert resumo["valor_em_aberto"] == Decimal("199.00")
    assert resumo["autorizacoes_ativas"] == 1
    servicos.processar_retorno(cobranca, "pago", {})
    resumo = servicos.resumo_da_cobranca(aluno.rede)
    assert resumo["pagas"] == 1 and resumo["taxa_de_sucesso"] == 100.0
    assert resumo["valor_recebido"] == Decimal("199.00")


# ------------------------------------------------------------------ webhook e telas


def test_webhook_exige_token_configurado(client, aluno, settings):
    settings.COBRANCA_WEBHOOK_TOKEN = ""
    resposta = client.post(reverse("cobranca:webhook"), data="{}", content_type="application/json")
    assert resposta.status_code == 503


def test_webhook_recusa_token_errado(client, aluno, settings, autorizacao_ativa=None):
    settings.COBRANCA_WEBHOOK_TOKEN = "segredo-certo"
    resposta = client.post(
        reverse("cobranca:webhook"),
        data="{}",
        content_type="application/json",
        HTTP_X_TOKEN="errado",
    )
    assert resposta.status_code == 403


def test_webhook_confirmou_pagamento(client, aluno, settings):
    import json

    settings.COBRANCA_WEBHOOK_TOKEN = "segredo-certo"
    autorizacao_ativa(aluno)
    cobranca = cobranca_do_mes(aluno)
    resposta = client.post(
        reverse("cobranca:webhook"),
        data=json.dumps({"cobranca": cobranca.pk, "situacao": "pago", "id": "PSP-9"}),
        content_type="application/json",
        HTTP_X_TOKEN="segredo-certo",
    )
    assert resposta.status_code == 200
    cobranca.refresh_from_db()
    assert cobranca.situacao == CobrancaRecorrente.Situacao.PAGA


def test_telas_da_cobranca_abrem(cliente_painel, aluno):
    autorizacao_ativa(aluno)
    cobranca_do_mes(aluno)
    for rota in ("cobranca:painel", "cobranca:lista", "cobranca:autorizacoes"):
        assert cliente_painel.get(reverse(rota)).status_code == 200, rota


def test_gerar_pela_tela_em_simulacao_avisa_que_nada_foi_gravado(cliente_painel, aluno):
    autorizacao_ativa(aluno)
    resposta = cliente_painel.post(
        reverse("cobranca:gerar"), {"dry_run": "1", "dia_do_vencimento": "10"}
    )
    assert resposta.status_code == 200
    assert "nada foi gravado" in resposta.content.decode()
    assert CobrancaRecorrente.objects.count() == 0


def test_gerar_pela_tela_grava(cliente_painel, aluno):
    autorizacao_ativa(aluno)
    cliente_painel.post(reverse("cobranca:gerar"), {"dia_do_vencimento": "5"})
    cobranca = CobrancaRecorrente.objects.get(aluno=aluno)
    assert cobranca.vencimento.day == 5


def test_cobranca_de_outra_rede_nao_aparece(cliente_painel, outra_rede, aluno):
    outro = CobrancaRecorrente.objects.create(
        rede=outra_rede,
        aluno=aluno,
        competencia=timezone.localdate().replace(day=1),
        valor=Decimal("10.00"),
        vencimento=timezone.localdate(),
    )
    resposta = cliente_painel.post(reverse("cobranca:enviar", args=[outro.pk]))
    assert resposta.status_code == 404


def test_aluno_nao_entra_na_cobranca(client, aluno):
    client.force_login(aluno.user)
    assert client.get(reverse("cobranca:painel")).status_code == 403
