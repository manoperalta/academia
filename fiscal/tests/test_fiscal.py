"""Testes do fiscal: calculo, emissao, cancelamento, PDF e telas."""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.urls import reverse

from fiscal import servicos
from fiscal.models import EventoFiscal, NotaFiscal
from fiscal.servicos import ErroFiscal

pytestmark = pytest.mark.django_db


# ------------------------------------------------------------------ configuracao e calculo


def test_configuracao_recusa_aliquota_fora_de_faixa(rede):
    with pytest.raises(ErroFiscal):
        servicos.configurar_fiscal(rede=rede, aliquota_iss=Decimal("40.00"))


def test_configuracao_recusa_codigo_de_servico_invalido(rede):
    with pytest.raises(ErroFiscal):
        servicos.configurar_fiscal(rede=rede, codigo_do_servico="abc")


def test_iss_calculado_sobre_o_valor(configuracao):
    conta = servicos.calcular_tributos(Decimal("200.00"), configuracao)
    assert conta["valor_do_iss"] == Decimal("10.00")
    assert conta["valor_liquido"] == Decimal("200.00"), "sem retencao, o liquido e o valor"
    assert any("ISS" in linha for linha in conta["memoria"])


def test_retencoes_federais_quando_configuradas(rede):
    configuracao = servicos.configurar_fiscal(
        rede=rede,
        aliquota_iss=Decimal("5.00"),
        retem_pis_cofins_csll=True,
        retem_ir=True,
        retem_inss=True,
    )
    conta = servicos.calcular_tributos(Decimal("200.00"), configuracao)
    assert conta["retencoes"]["pis"] == "1.30"
    assert conta["retencoes"]["cofins"] == "6.00"
    assert conta["retencoes"]["csll"] == "2.00"
    assert conta["retencoes"]["ir"] == "3.00"
    assert conta["retencoes"]["inss"] == "22.00"
    assert conta["valor_liquido"] == Decimal("165.70")


# ------------------------------------------------------------------ emissao


def test_emitir_nota_gera_numero_sequencial_e_codigo(configuracao, rede, unidade, aluno, pagamento):
    primeira = servicos.emitir_nota(
        rede=rede, valor=Decimal("200.00"), aluno=aluno, unidade=unidade, pagamento=pagamento
    )
    assert primeira.numero == "1" and primeira.serie == "1"
    assert primeira.situacao == NotaFiscal.Situacao.EMITIDA
    assert len(primeira.codigo_de_verificacao) == 32
    assert primeira.valor_do_iss == Decimal("10.00")
    assert EventoFiscal.objects.filter(nota=primeira, tipo=EventoFiscal.Tipo.EMITIDA).exists()


def test_emitir_declara_modo_simulado(configuracao, rede, aluno, pagamento):
    nota = servicos.emitir_nota(
        rede=rede, valor=Decimal("200.00"), aluno=aluno, pagamento=pagamento
    )
    assert nota.provedor == "simulado"
    assert "simulad" in nota.resposta_do_provedor["aviso"].lower()


def test_nota_duplicada_para_o_mesmo_pagamento_e_recusada(configuracao, rede, aluno, pagamento):
    servicos.emitir_nota(rede=rede, valor=Decimal("200.00"), aluno=aluno, pagamento=pagamento)
    with pytest.raises(ErroFiscal):
        servicos.emitir_nota(rede=rede, valor=Decimal("200.00"), aluno=aluno, pagamento=pagamento)


def test_sem_configuracao_fiscal_nao_emite(rede, aluno):
    with pytest.raises(ErroFiscal):
        servicos.emitir_nota(rede=rede, valor=Decimal("200.00"), aluno=aluno)


def test_valor_zero_e_recusado(configuracao, rede, aluno):
    with pytest.raises(ErroFiscal):
        servicos.emitir_nota(rede=rede, valor=Decimal("0.00"), aluno=aluno)


def test_provedor_nao_integrado_deixa_a_nota_com_erro(rede, aluno):
    servicos.configurar_fiscal(rede=rede, aliquota_iss=Decimal("5.00"), provedor="nacional")
    nota = servicos.emitir_nota(rede=rede, valor=Decimal("200.00"), aluno=aluno)
    assert nota.situacao == NotaFiscal.Situacao.ERRO
    assert nota.numero == ""
    assert EventoFiscal.objects.filter(nota=nota, tipo=EventoFiscal.Tipo.ERRO).exists()


# ------------------------------------------------------------------ cancelamento


def test_cancelar_exige_motivo(configuracao, rede, aluno, pagamento):
    nota = servicos.emitir_nota(
        rede=rede, valor=Decimal("200.00"), aluno=aluno, pagamento=pagamento
    )
    with pytest.raises(ErroFiscal):
        servicos.cancelar_nota(nota, "   ")


def test_cancelar_nota_emitida(configuracao, rede, aluno, pagamento):
    nota = servicos.emitir_nota(
        rede=rede, valor=Decimal("200.00"), aluno=aluno, pagamento=pagamento
    )
    servicos.cancelar_nota(nota, "servico cancelado pelo aluno")
    nota.refresh_from_db()
    assert nota.situacao == NotaFiscal.Situacao.CANCELADA
    assert nota.motivo_do_cancelamento == "servico cancelado pelo aluno"
    with pytest.raises(ErroFiscal):
        servicos.cancelar_nota(nota, "de novo")


# ------------------------------------------------------------------ lote e resumo


def test_lote_emite_uma_nota_por_pagamento_e_nao_duplica(configuracao, rede, pagamento):
    competencia = pagamento.data_inicio
    primeiro = servicos.emitir_notas_da_competencia(rede, competencia)
    assert len(primeiro["emitidas"]) == 1
    segundo = servicos.emitir_notas_da_competencia(rede, competencia)
    assert segundo["emitidas"] == []
    assert segundo["ja_tinham_nota"] == [pagamento.pk]
    assert NotaFiscal.objects.filter(rede=rede).count() == 1


def test_lote_em_simulacao_nao_grava(configuracao, rede, pagamento):
    resultado = servicos.emitir_notas_da_competencia(rede, pagamento.data_inicio, dry_run=True)
    assert resultado["dry_run"] is True and len(resultado["emitidas"]) == 1
    assert NotaFiscal.objects.count() == 0


def test_resumo_fiscal_soma_faturado_iss_e_liquido(configuracao, rede, aluno, pagamento):
    servicos.emitir_nota(
        rede=rede,
        valor=Decimal("200.00"),
        aluno=aluno,
        pagamento=pagamento,
        competencia=pagamento.data_inicio,
    )
    resumo = servicos.resumo_fiscal(rede, pagamento.data_inicio)
    assert resumo["emitidas"] == 1
    assert resumo["valor_faturado"] == Decimal("200.00")
    assert resumo["valor_do_iss"] == Decimal("10.00")
    assert resumo["liquido"] == Decimal("200.00")
    assert resumo["sem_nota"] == 0


# ------------------------------------------------------------------ PDF e telas


def test_pdf_da_nota_e_um_pdf_com_os_valores(configuracao, rede, aluno, pagamento):
    nota = servicos.emitir_nota(
        rede=rede, valor=Decimal("200.00"), aluno=aluno, pagamento=pagamento
    )
    conteudo = servicos.pdf_da_nota(nota)
    assert conteudo.startswith(b"%PDF-1.4")
    assert b"/Type /Catalog" in conteudo
    assert b"R$ 200,00" in conteudo
    assert b"R$ 10,00" in conteudo
    texto = conteudo.lower()
    assert b"simulado" in texto or b"simulada" in texto


def test_telas_do_fiscal_abrem(cliente_painel, configuracao, pagamento):
    servicos.emitir_nota(
        rede=pagamento.rede,
        valor=Decimal("200.00"),
        aluno=None,
        pagamento=pagamento,
        competencia=pagamento.data_inicio,
    )
    nota = NotaFiscal.objects.first()
    for rota in ("fiscal:painel", "fiscal:notas"):
        assert cliente_painel.get(reverse(rota)).status_code == 200, rota
    assert cliente_painel.get(reverse("fiscal:nota", args=[nota.pk])).status_code == 200


def test_pdf_pela_tela(cliente_painel, configuracao, pagamento):
    nota = servicos.emitir_nota(
        rede=pagamento.rede,
        valor=Decimal("200.00"),
        aluno=None,
        pagamento=pagamento,
        competencia=pagamento.data_inicio,
    )
    resposta = cliente_painel.get(reverse("fiscal:pdf", args=[nota.pk]))
    assert resposta.status_code == 200
    assert resposta["Content-Type"] == "application/pdf"
    assert resposta.content.startswith(b"%PDF")


def test_simulacao_pela_tela_avisa_que_nada_foi_gravado(cliente_painel, configuracao, pagamento):
    resposta = cliente_painel.post(reverse("fiscal:lote"), {"dry_run": "1"})
    assert resposta.status_code == 200
    assert "nada foi gravado" in resposta.content.decode()
    assert NotaFiscal.objects.count() == 0


def test_cancelar_pela_tela_exige_motivo(cliente_painel, configuracao, pagamento):
    nota = servicos.emitir_nota(
        rede=pagamento.rede,
        valor=Decimal("200.00"),
        aluno=None,
        pagamento=pagamento,
        competencia=pagamento.data_inicio,
    )
    cliente_painel.post(reverse("fiscal:cancelar", args=[nota.pk]), {"motivo": ""})
    nota.refresh_from_db()
    assert nota.situacao == NotaFiscal.Situacao.EMITIDA
    cliente_painel.post(reverse("fiscal:cancelar", args=[nota.pk]), {"motivo": "erro de valor"})
    nota.refresh_from_db()
    assert nota.situacao == NotaFiscal.Situacao.CANCELADA


def test_nota_de_outra_rede_nao_abre(cliente_painel, outra_rede, aluno, pagamento):
    from django.contrib.auth import get_user_model

    from core.models import Unidade
    from usuarios.models import Usuario

    unidade_alheia = Unidade.objects.create(rede=outra_rede, nome="Filial", codigo="filial")
    login = get_user_model().objects.create_user(
        username="alheio.fiscal", password="SenhaAlheia!23"
    )
    alheio = Usuario.todos.create(
        rede=outra_rede, unidade=unidade_alheia, user=login, nome="Alheio", status_user="Ativo"
    )
    servicos.configurar_fiscal(rede=outra_rede, aliquota_iss=Decimal("5.00"))
    nota_alheia = servicos.emitir_nota(rede=outra_rede, valor=Decimal("10.00"), aluno=alheio)
    assert cliente_painel.get(reverse("fiscal:nota", args=[nota_alheia.pk])).status_code == 404
    assert cliente_painel.get(reverse("fiscal:pdf", args=[nota_alheia.pk])).status_code == 404


def test_aluno_nao_entra_no_fiscal(client, aluno):
    client.force_login(aluno.user)
    assert client.get(reverse("fiscal:painel")).status_code == 403
