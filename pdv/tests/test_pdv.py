"""Testes do PDV: produto, estoque, venda e indicadores."""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.urls import reverse

from pdv import servicos
from pdv.models import MovimentoDeEstoque, Produto, Venda
from pdv.servicos import ErroDePdv

pytestmark = pytest.mark.django_db


def test_cadastro_exige_nome_e_preco(rede):
    with pytest.raises(ErroDePdv):
        servicos.cadastrar_produto(rede=rede, nome="  ", preco_de_venda=Decimal("10.00"))
    with pytest.raises(ErroDePdv):
        servicos.cadastrar_produto(rede=rede, nome="Coisa", preco_de_venda=Decimal("0.00"))


def test_cadastro_com_estoque_inicial_gera_movimento(produto):
    assert produto.estoque_atual == 10
    movimento = MovimentoDeEstoque.objects.get(produto=produto)
    assert movimento.tipo == MovimentoDeEstoque.Tipo.ENTRADA
    assert movimento.saldo_apos == 10
    assert "inicial" in movimento.motivo


def test_cadastrar_de_novo_atualiza_o_mesmo_produto(rede, produto):
    atualizado = servicos.cadastrar_produto(
        rede=rede, nome="Whey 900g", preco_de_venda=Decimal("190.00"), custo=Decimal("130.00")
    )
    assert atualizado.pk == produto.pk
    assert atualizado.preco_de_venda == Decimal("190.00")
    assert Produto.objects.filter(rede=rede).count() == 1


def test_entrada_de_estoque_soma_e_registra(produto):
    servicos.registrar_entrada(produto=produto, quantidade=5, motivo="compra")
    produto.refresh_from_db()
    assert produto.estoque_atual == 15
    ultimo = MovimentoDeEstoque.objects.filter(produto=produto).first()
    assert ultimo.tipo == MovimentoDeEstoque.Tipo.ENTRADA and ultimo.saldo_apos == 15


def test_ajuste_exige_motivo_e_diferenca(produto):
    with pytest.raises(ErroDePdv):
        servicos.ajustar_estoque(produto=produto, novo_saldo=8, motivo="")
    with pytest.raises(ErroDePdv):
        servicos.ajustar_estoque(produto=produto, novo_saldo=10, motivo="conferencia")
    servicos.ajustar_estoque(produto=produto, novo_saldo=8, motivo="quebra de frasco")
    produto.refresh_from_db()
    assert produto.estoque_atual == 8
    movimento = MovimentoDeEstoque.objects.filter(produto=produto).first()
    assert movimento.tipo == MovimentoDeEstoque.Tipo.AJUSTE and movimento.quantidade == -2


def test_venda_nao_baixa_estoque_antes_de_finalizar(rede, unidade, aluno, produto, admin_do_painel):
    venda = servicos.abrir_venda(
        rede=rede, unidade=unidade, aluno=aluno, criada_por=admin_do_painel
    )
    servicos.adicionar_item(venda=venda, produto=produto, quantidade=2)
    produto.refresh_from_db()
    assert produto.estoque_atual == 10, "a baixa so acontece na finalizacao"
    assert venda.total == Decimal("360.00")


def test_abrir_venda_reaproveita_a_aberta_do_operador(rede, unidade, admin_do_painel):
    primeira = servicos.abrir_venda(rede=rede, unidade=unidade, criada_por=admin_do_painel)
    segunda = servicos.abrir_venda(rede=rede, unidade=unidade, criada_por=admin_do_painel)
    assert primeira.pk == segunda.pk


def test_estoque_insuficiente_impede_o_item(rede, unidade, produto, admin_do_painel):
    venda = servicos.abrir_venda(rede=rede, criada_por=admin_do_painel)
    with pytest.raises(ErroDePdv):
        servicos.adicionar_item(venda=venda, produto=produto, quantidade=11)
    servicos.adicionar_item(venda=venda, produto=produto, quantidade=8)
    with pytest.raises(ErroDePdv):
        servicos.adicionar_item(venda=venda, produto=produto, quantidade=3)


def test_produto_de_outra_rede_nao_entra_na_venda(outra_rede, rede, admin_do_painel):
    from core.models import Unidade

    unidade_alheia = Unidade.objects.create(rede=outra_rede, nome="Filial", codigo="filial")
    alheio = servicos.cadastrar_produto(
        rede=outra_rede,
        unidade=unidade_alheia,
        nome="Produto X",
        preco_de_venda=Decimal("10.00"),
        estoque_inicial=5,
    )
    venda = servicos.abrir_venda(rede=rede, criada_por=admin_do_painel)
    with pytest.raises(ErroDePdv):
        servicos.adicionar_item(venda=venda, produto=alheio)


def test_desconto_maior_que_o_total_e_recusado(rede, produto, admin_do_painel):
    venda = servicos.abrir_venda(rede=rede, criada_por=admin_do_painel)
    servicos.adicionar_item(venda=venda, produto=produto, quantidade=1)
    with pytest.raises(ErroDePdv):
        servicos.aplicar_desconto(venda=venda, desconto=Decimal("500.00"))
    servicos.aplicar_desconto(venda=venda, desconto=Decimal("30.00"))
    assert venda.total == Decimal("150.00")


def test_finalizar_baixa_estoque_e_registra_movimentos(
    rede, unidade, aluno, produto, admin_do_painel
):
    venda = servicos.abrir_venda(
        rede=rede, unidade=unidade, aluno=aluno, criada_por=admin_do_painel
    )
    servicos.adicionar_item(venda=venda, produto=produto, quantidade=2)
    servicos.finalizar_venda(venda=venda, forma_de_pagamento="pix", criado_por=admin_do_painel)
    produto.refresh_from_db()
    venda.refresh_from_db()
    assert venda.situacao == Venda.Situacao.FINALIZADA
    assert venda.forma_de_pagamento == "pix"
    assert produto.estoque_atual == 8
    saida = MovimentoDeEstoque.objects.filter(
        venda=venda, tipo=MovimentoDeEstoque.Tipo.SAIDA
    ).first()
    assert saida is not None and saida.quantidade == -2 and saida.saldo_apos == 8


def test_finalizar_sem_item_e_recusado(rede, admin_do_painel):
    venda = servicos.abrir_venda(rede=rede, criada_por=admin_do_painel)
    with pytest.raises(ErroDePdv):
        servicos.finalizar_venda(venda=venda, forma_de_pagamento="dinheiro")


def test_finalizar_duas_vezes_e_recusado(rede, produto, admin_do_painel):
    venda = servicos.abrir_venda(rede=rede, criada_por=admin_do_painel)
    servicos.adicionar_item(venda=venda, produto=produto, quantidade=1)
    servicos.finalizar_venda(venda=venda, forma_de_pagamento="dinheiro")
    with pytest.raises(ErroDePdv):
        servicos.finalizar_venda(venda=venda, forma_de_pagamento="dinheiro")


def test_cancelar_venda_finalizada_devolve_estoque(rede, produto, admin_do_painel):
    venda = servicos.abrir_venda(rede=rede, criada_por=admin_do_painel)
    servicos.adicionar_item(venda=venda, produto=produto, quantidade=3)
    servicos.finalizar_venda(venda=venda, forma_de_pagamento="debito")
    produto.refresh_from_db()
    assert produto.estoque_atual == 7
    servicos.cancelar_venda(venda=venda, motivo="cliente desistiu", criado_por=admin_do_painel)
    produto.refresh_from_db()
    venda.refresh_from_db()
    assert produto.estoque_atual == 10
    assert venda.situacao == Venda.Situacao.CANCELADA
    assert MovimentoDeEstoque.objects.filter(
        venda=venda, tipo=MovimentoDeEstoque.Tipo.DEVOLUCAO
    ).exists()


def test_resumo_do_pdv_com_ticket_medio_e_mais_vendidos(rede, unidade, produto, admin_do_painel):
    outro = servicos.cadastrar_produto(
        rede=rede, unidade=unidade, nome="Cinta", preco_de_venda=Decimal("90.00"), estoque_inicial=5
    )
    for produto_, quantidade, forma in ((produto, 2, "pix"), (outro, 1, "dinheiro")):
        venda = Venda.objects.create(rede=rede, unidade=unidade, criada_por=admin_do_painel)
        servicos.adicionar_item(venda=venda, produto=produto_, quantidade=quantidade)
        servicos.finalizar_venda(venda=venda, forma_de_pagamento=forma, criado_por=admin_do_painel)
    resumo = servicos.resumo_do_pdv(rede)
    assert resumo["vendas"] == 2
    assert resumo["faturamento"] == Decimal("450.00")
    assert resumo["ticket_medio"] == Decimal("225.00")
    assert resumo["mais_vendidos"][0]["produto"] == "Whey 900g"
    assert resumo["por_forma_de_pagamento"]["pix"] == Decimal("360.00")


def test_alerta_de_estoque_minimo(rede, produto, admin_do_painel):
    assert servicos.produtos_abaixo_do_minimo(rede) == []
    servicos.registrar_movimento(produto=produto, tipo="saida", quantidade=8, motivo="venda balcao")
    produto.refresh_from_db()
    assert produto.estoque_atual == 2
    assert [item.pk for item in servicos.produtos_abaixo_do_minimo(rede)] == [produto.pk]


def test_telas_do_pdv_abrem(cliente_painel, rede, produto):
    for rota in ("pdv:painel", "pdv:produtos", "pdv:balcao", "pdv:vendas", "pdv:movimentos"):
        assert cliente_painel.get(reverse(rota)).status_code == 200, rota


def test_fluxo_do_balcao_pelas_telas(cliente_painel, rede, unidade, produto, admin_do_painel):

    cliente_painel.post(
        reverse("pdv:salvar_produto"),
        {
            "nome": "Coqueteleira",
            "preco_de_venda": "35.00",
            "custo": "18.00",
            "estoque_inicial": "4",
            "estoque_minimo": "1",
        },
    )
    coqueteleira = Produto.objects.get(rede=rede, nome="Coqueteleira")
    venda = servicos.abrir_venda(rede=rede, unidade=unidade, criada_por=admin_do_painel)
    cliente_painel.post(
        reverse("pdv:adicionar_item"),
        {"venda": venda.pk, "produto": coqueteleira.pk, "quantidade": 1},
    )
    cliente_painel.post(reverse("pdv:desconto", args=[venda.pk]), {"desconto": "5.00"})
    resposta = cliente_painel.post(
        reverse("pdv:finalizar", args=[venda.pk]), {"forma_de_pagamento": "pix"}
    )
    assert resposta.status_code == 302
    venda.refresh_from_db()
    coqueteleira.refresh_from_db()
    assert venda.situacao == Venda.Situacao.FINALIZADA and venda.total == Decimal("30.00")
    assert coqueteleira.estoque_atual == 3
    assert cliente_painel.get(reverse("pdv:venda", args=[venda.pk])).status_code == 200


def test_produto_de_outra_rede_nao_movimenta(cliente_painel, outra_rede):
    alheio = servicos.cadastrar_produto(
        rede=outra_rede, nome="Produto Alheio", preco_de_venda=Decimal("10.00"), estoque_inicial=1
    )
    assert (
        cliente_painel.post(
            reverse("pdv:movimentar", args=[alheio.pk]), {"quantidade": 1}
        ).status_code
        == 404
    )


def test_aluno_nao_entra_no_pdv(client, aluno):
    client.force_login(aluno.user)
    assert client.get(reverse("pdv:painel")).status_code == 403
