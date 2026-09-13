"""Repasse/royalty: cálculo, memória linha a linha, reprodutibilidade e conciliação."""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from rede.models import ItemDeRepasse, RegraDeRepasse, Repasse
from rede.servicos import (
    ErroDeRede, calcular_repasse, conferir_repasse, emitir_repasse, emitir_repasses_do_mes,
    marcar_repasse_pago, periodo_do_mes, regra_para, relatorio_de_repasses,
)


@pytest.fixture
def regra_padrao(db, rede):
    return RegraDeRepasse.objects.create(rede=rede, unidade=None, tipo=RegraDeRepasse.Tipo.PERCENTUAL,
                                         percentual=Decimal("8.000"), base=RegraDeRepasse.Base.BRUTO,
                                         fundo_de_marketing=Decimal("2.00"), piso_minimo=Decimal("0.00"))


def test_calculo_bruto_com_fundo_e_memoria(db, rede, unidades, receita, regra_padrao):
    inicio, fim = periodo_do_mes()
    calculo = calcular_repasse(unidades[0], inicio, fim)
    receita_da_unidade = Decimal("450.00")  # 3 alunos pagos de 150
    assert calculo["receita_bruta"] == receita_da_unidade
    assert calculo["base_de_calculo"] == receita_da_unidade  # base bruta
    assert calculo["royalty"] == Decimal("36.00")            # 8%
    assert calculo["fundo"] == Decimal("9.00")               # 2%
    assert calculo["valor_devido"] == Decimal("45.00")
    tipos = [linha["tipo"] for linha in calculo["linhas"]]
    assert ItemDeRepasse.Tipo.RECEITA in tipos and ItemDeRepasse.Tipo.ROYALTY in tipos
    assert ItemDeRepasse.Tipo.FUNDO in tipos


def test_base_liquida_exclui_taxas_e_estornos(db, rede, unidades, receita):
    RegraDeRepasse.objects.create(
        rede=rede, unidade=None, tipo=RegraDeRepasse.Tipo.PERCENTUAL, percentual=Decimal("10.000"),
        base=RegraDeRepasse.Base.LIQUIDO, percentual_de_taxas_de_gateway=Decimal("3.00"),
        excluir_taxas_de_gateway=True, excluir_estornos=True,
    )
    inicio, fim = periodo_do_mes()
    calculo = calcular_repasse(unidades[0], inicio, fim)
    assert calculo["exclusoes"] == Decimal("13.50")                 # 3% de 450
    assert calculo["base_de_calculo"] == Decimal("436.50")
    assert calculo["royalty"] == Decimal("43.65")
    exclusoes = [linha for linha in calculo["linhas"] if linha["tipo"] == ItemDeRepasse.Tipo.EXCLUSAO]
    assert exclusoes and "gateway" in exclusoes[0]["descricao"]


def test_piso_minimo_ajusta_o_total(db, rede, unidades, receita):
    RegraDeRepasse.objects.create(rede=rede, unidade=None, tipo=RegraDeRepasse.Tipo.PERCENTUAL,
                                  percentual=Decimal("1.000"), piso_minimo=Decimal("100.00"))
    inicio, fim = periodo_do_mes()
    calculo = calcular_repasse(unidades[0], inicio, fim)
    assert calculo["piso_aplicado"] is True
    assert calculo["valor_devido"] == Decimal("100.00")
    assert any(linha["tipo"] == ItemDeRepasse.Tipo.PISO for linha in calculo["linhas"])


def test_regra_da_unidade_tem_prioridade(db, rede, unidades, receita, regra_padrao):
    RegraDeRepasse.objects.create(rede=rede, unidade=unidades[0], tipo=RegraDeRepasse.Tipo.FIXO,
                                  valor_fixo=Decimal("500.00"))
    assert regra_para(unidades[0]).tipo == RegraDeRepasse.Tipo.FIXO
    assert regra_para(unidades[1]).tipo == RegraDeRepasse.Tipo.PERCENTUAL


def test_sem_regra_o_calculo_recusa_com_mensagem(db, rede, unidades, receita):
    with pytest.raises(ErroDeRede):
        calcular_repasse(unidades[0], *periodo_do_mes())


def test_emissao_e_idempotente(db, rede, unidades, receita, regra_padrao):
    inicio, fim = periodo_do_mes()
    primeiro = emitir_repasse(unidades[0], inicio, fim)
    segundo = emitir_repasse(unidades[0], inicio, fim)
    assert primeiro.pk == segundo.pk
    assert Repasse.objects.count() == 1
    assert primeiro.hash_do_calculo
    assert primeiro.itens.count() == len(primeiro.memoria["linhas"])


def test_recalculo_gera_o_mesmo_numero(db, rede, unidades, receita, regra_padrao):
    inicio, fim = periodo_do_mes()
    repasse = emitir_repasse(unidades[0], inicio, fim)
    conferencia = conferir_repasse(repasse)
    assert conferencia["ok"] is True
    assert conferencia["mesmo_numero"] is True
    assert not conferencia["divergencias"]


def test_conferencia_detecta_valor_alterado(db, rede, unidades, receita, regra_padrao):
    inicio, fim = periodo_do_mes()
    repasse = emitir_repasse(unidades[0], inicio, fim)
    Repasse.objects.filter(pk=repasse.pk).update(valor_devido=Decimal("1.00"))
    repasse.refresh_from_db()
    conferencia = conferir_repasse(repasse)
    assert conferencia["ok"] is False
    assert any(divergencia["linha"] == "Total devido" for divergencia in conferencia["divergencias"])


def test_emissao_do_mes_para_a_rede(db, rede, unidades, receita, regra_padrao):
    resultado = emitir_repasses_do_mes(rede)
    assert len(resultado["emitidos"]) == 3
    assert Decimal(resultado["total"]) > 0
    assert not resultado["erros"]
    relatorio = relatorio_de_repasses(rede, *periodo_do_mes())
    assert relatorio["total_devido"] == Decimal(resultado["total"])


def test_baixa_e_atraso(db, rede, unidades, receita, regra_padrao):
    inicio, fim = periodo_do_mes()
    repasse = emitir_repasse(unidades[0], inicio, fim)
    Repasse.objects.filter(pk=repasse.pk).update(vencimento=timezone.localdate() - timedelta(days=5))
    repasse.refresh_from_db()
    assert repasse.atrasado is True
    from rede.servicos import atualizar_atrasados

    assert atualizar_atrasados(rede) == 1
    repasse.refresh_from_db()
    assert repasse.situacao == Repasse.Situacao.ATRASADO
    marcar_repasse_pago(repasse, repasse.valor_devido)
    repasse.refresh_from_db()
    assert repasse.situacao == Repasse.Situacao.PAGO
    assert repasse.saldo == Decimal("0.00")
