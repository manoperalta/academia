"""Servicos do PDV: produto, estoque, venda e indicadores.

A baixa de estoque acontece **na finalizacao**, dentro de transacao: ou a venda inteira entra, ou
nada entra. Venda pela metade com estoque baixado e o pior dos dois mundos.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from pdv.models import ItemDaVenda, MovimentoDeEstoque, Produto, Venda


class ErroDePdv(Exception):
    """Falha esperada no PDV."""


def cadastrar_produto(
    *,
    rede,
    nome: str,
    preco_de_venda,
    custo=Decimal("0"),
    codigo: str = "",
    estoque_inicial: int = 0,
    estoque_minimo: int = 0,
    unidade=None,
) -> Produto:
    if not (nome or "").strip():
        raise ErroDePdv("Informe o nome do produto.")
    if Decimal(str(preco_de_venda or 0)) <= 0:
        raise ErroDePdv("Informe o preco de venda.")
    produto, criado = Produto.objects.get_or_create(
        rede=rede,
        nome=nome.strip(),
        defaults={
            "unidade": unidade,
            "preco_de_venda": preco_de_venda,
            "custo": custo,
            "codigo": codigo,
            "estoque_minimo": estoque_minimo,
        },
    )
    if not criado:
        produto.unidade = unidade or produto.unidade
        produto.preco_de_venda = preco_de_venda
        produto.custo = custo
        produto.estoque_minimo = estoque_minimo
        produto.codigo = codigo or produto.codigo
        produto.ativo = True
        produto.save()
    if estoque_inicial:
        registrar_entrada(produto=produto, quantidade=estoque_inicial, motivo="estoque inicial")
    return produto


def registrar_movimento(
    *, produto: Produto, tipo: str, quantidade: int, motivo: str = "", venda=None, criado_por=None
) -> MovimentoDeEstoque:
    if tipo not in dict(MovimentoDeEstoque.Tipo.choices):
        raise ErroDePdv("Tipo de movimento desconhecido.")
    if quantidade == 0:
        raise ErroDePdv("Quantidade do movimento nao pode ser zero.")
    if tipo == MovimentoDeEstoque.Tipo.SAIDA and quantidade > 0:
        quantidade = -quantidade
    if tipo == MovimentoDeEstoque.Tipo.ENTRADA and quantidade < 0:
        quantidade = -quantidade
    saldo = produto.estoque_atual + quantidade
    if saldo < 0:
        raise ErroDePdv(
            f"Estoque insuficiente de {produto.nome}: tem {produto.estoque_atual}, "
            f"o movimento precisa de {abs(quantidade)}."
        )
    produto.estoque_atual = saldo
    produto.save(update_fields=["estoque_atual"])
    return MovimentoDeEstoque.objects.create(
        produto=produto,
        tipo=tipo,
        quantidade=quantidade,
        saldo_apos=saldo,
        motivo=motivo,
        venda=venda,
        criado_por=criado_por,
    )


def registrar_entrada(*, produto: Produto, quantidade: int, motivo: str = "", criado_por=None):
    return registrar_movimento(
        produto=produto,
        tipo=MovimentoDeEstoque.Tipo.ENTRADA,
        quantidade=quantidade,
        motivo=motivo or "entrada de mercadoria",
        criado_por=criado_por,
    )


def ajustar_estoque(*, produto: Produto, novo_saldo: int, motivo: str, criado_por=None):
    if not (motivo or "").strip():
        raise ErroDePdv("O ajuste de inventario exige motivo.")
    diferenca = int(novo_saldo) - produto.estoque_atual
    if diferenca == 0:
        raise ErroDePdv("O saldo informado e igual ao atual.")
    return registrar_movimento(
        produto=produto,
        tipo=MovimentoDeEstoque.Tipo.AJUSTE,
        quantidade=diferenca,
        motivo=motivo,
        criado_por=criado_por,
    )


def abrir_venda(*, rede, unidade=None, aluno=None, criada_por=None) -> Venda:
    aberta = Venda.objects.filter(
        rede=rede, criada_por=criada_por, situacao=Venda.Situacao.ABERTA
    ).first()
    if aberta is not None:
        return aberta
    return Venda.objects.create(rede=rede, unidade=unidade, aluno=aluno, criada_por=criada_por)


def adicionar_item(*, venda: Venda, produto: Produto, quantidade: int = 1) -> ItemDaVenda:
    if venda.situacao != Venda.Situacao.ABERTA:
        raise ErroDePdv("Esta venda nao esta aberta.")
    if quantidade <= 0:
        raise ErroDePdv("Quantidade precisa ser maior que zero.")
    if produto.rede_id != venda.rede_id:
        raise ErroDePdv("Produto de outra rede nao entra nesta venda.")
    ja_na_venda = sum(item.quantidade for item in venda.itens.filter(produto=produto))
    if ja_na_venda + quantidade > produto.estoque_atual:
        raise ErroDePdv(
            f"Estoque insuficiente de {produto.nome}: disponivel {produto.estoque_atual}."
        )
    item = venda.itens.filter(produto=produto, preco_unitario=produto.preco_de_venda).first()
    if item is None:
        item = ItemDaVenda.objects.create(
            venda=venda,
            produto=produto,
            quantidade=quantidade,
            preco_unitario=produto.preco_de_venda,
        )
    else:
        item.quantidade += quantidade
        item.save(update_fields=["quantidade"])
    item.calcular_subtotal()
    venda.recalcular()
    return item


def remover_item(*, venda: Venda, item: ItemDaVenda) -> Venda:
    if venda.situacao != Venda.Situacao.ABERTA:
        raise ErroDePdv("Esta venda nao esta aberta.")
    item.delete()
    venda.recalcular()
    return venda


def aplicar_desconto(*, venda: Venda, desconto) -> Venda:
    if venda.situacao != Venda.Situacao.ABERTA:
        raise ErroDePdv("Esta venda nao esta aberta.")
    valor = Decimal(str(desconto or 0))
    if valor < 0:
        raise ErroDePdv("Desconto nao pode ser negativo.")
    subtotal = sum(item.subtotal for item in venda.itens.all()) or Decimal("0")
    if valor > subtotal:
        raise ErroDePdv("Desconto maior que o total da venda.")
    venda.desconto = valor
    venda.save(update_fields=["desconto"])
    return venda.recalcular()


@transaction.atomic
def finalizar_venda(*, venda: Venda, forma_de_pagamento: str, criado_por=None) -> Venda:
    """Baixa o estoque e fecha a venda — tudo em uma transacao."""
    if venda.situacao != Venda.Situacao.ABERTA:
        raise ErroDePdv("Esta venda ja foi finalizada ou cancelada.")
    itens = list(venda.itens.select_related("produto"))
    if not itens:
        raise ErroDePdv("Nao da para finalizar uma venda sem item.")
    if forma_de_pagamento not in dict(Venda.FormaDePagamento.choices):
        raise ErroDePdv("Forma de pagamento desconhecida.")
    for item in itens:
        if item.quantidade > item.produto.estoque_atual:
            raise ErroDePdv(
                f"Estoque insuficiente de {item.produto.nome}: "
                f"disponivel {item.produto.estoque_atual}."
            )
    for item in itens:
        registrar_movimento(
            produto=item.produto,
            tipo=MovimentoDeEstoque.Tipo.SAIDA,
            quantidade=item.quantidade,
            motivo=f"venda {venda.pk}",
            venda=venda,
            criado_por=criado_por,
        )
    venda.recalcular(salvar=False)
    venda.forma_de_pagamento = forma_de_pagamento
    venda.situacao = Venda.Situacao.FINALIZADA
    venda.finalizada_em = timezone.now()
    venda.save(update_fields=["forma_de_pagamento", "situacao", "finalizada_em", "total"])
    return venda


@transaction.atomic
def cancelar_venda(*, venda: Venda, motivo: str = "", criado_por=None) -> Venda:
    """Devolve o estoque dos itens e cancela a venda."""
    if venda.situacao == Venda.Situacao.CANCELADA:
        raise ErroDePdv("Esta venda ja esta cancelada.")
    for item in venda.itens.select_related("produto"):
        if venda.situacao == Venda.Situacao.FINALIZADA:
            registrar_movimento(
                produto=item.produto,
                tipo=MovimentoDeEstoque.Tipo.DEVOLUCAO,
                quantidade=item.quantidade,
                motivo=motivo or "cancelamento de venda",
                venda=venda,
                criado_por=criado_por,
            )
    venda.situacao = Venda.Situacao.CANCELADA
    venda.observacoes = (motivo or venda.observacoes)[:200]
    venda.save(update_fields=["situacao", "observacoes"])
    return venda


def produtos_abaixo_do_minimo(rede, limite: int = 50):
    return [
        produto
        for produto in Produto.objects.filter(rede=rede, ativo=True)[:limite]
        if produto.abaixo_do_minimo
    ]


def resumo_do_pdv(rede, dias: int = 30) -> dict:
    desde = timezone.now() - timedelta(days=dias)
    vendas = Venda.objects.filter(
        rede=rede, situacao=Venda.Situacao.FINALIZADA, finalizada_em__gte=desde
    )
    quantidade = vendas.count()
    total = vendas.aggregate(soma=Sum("total"))["soma"] or Decimal("0")
    itens = ItemDaVenda.objects.filter(venda__in=vendas).select_related("produto")
    por_produto: dict[str, dict] = {}
    for item in itens:
        registro = por_produto.setdefault(
            item.produto.nome, {"quantidade": 0, "valor": Decimal("0")}
        )
        registro["quantidade"] += item.quantidade
        registro["valor"] += item.subtotal
    mais_vendidos = sorted(
        ({"produto": nome, **dados} for nome, dados in por_produto.items()),
        key=lambda linha: (-linha["quantidade"], -linha["valor"]),
    )[:5]
    recebido = {
        forma: (
            vendas.filter(forma_de_pagamento=forma).aggregate(Sum("total"))["total__sum"]
            or Decimal("0")
        )
        for forma, _rotulo in Venda.FormaDePagamento.choices
    }
    return {
        "dias": dias,
        "vendas": quantidade,
        "faturamento": total,
        "ticket_medio": round(total / quantidade, 2) if quantidade else Decimal("0"),
        "itens_vendidos": sum(item.quantidade for item in itens),
        "mais_vendidos": mais_vendidos,
        "por_forma_de_pagamento": {forma: valor for forma, valor in recebido.items() if valor},
        "abaixo_do_minimo": len(produtos_abaixo_do_minimo(rede)),
        "em_aberto": Venda.objects.filter(rede=rede, situacao=Venda.Situacao.ABERTA).count(),
    }
