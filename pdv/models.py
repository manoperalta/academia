"""Modelos do PDV: produto, estoque, venda e item.

Duas decisoes que evitam dor de cabeca no caixa:

* **preco congelado no item** — mudar o preco do produto depois nao reescreve a venda de ontem;
* **estoque e movimento, nao um numero solto** — cada entrada, saida e ajuste vira linha, com o
  motivo escrito. Numero que muda sozinho nao se explica para o dono da loja.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

from core.models import Rede, Unidade


class Produto(models.Model):
    rede = models.ForeignKey(Rede, on_delete=models.CASCADE, related_name="produtos")
    unidade = models.ForeignKey(
        Unidade, on_delete=models.SET_NULL, null=True, blank=True, related_name="produtos"
    )
    nome = models.CharField("nome", max_length=150)
    codigo = models.CharField("codigo ou codigo de barras", max_length=60, blank=True)
    preco_de_venda = models.DecimalField(
        "preco de venda", max_digits=10, decimal_places=2, default=0
    )
    custo = models.DecimalField("custo", max_digits=10, decimal_places=2, default=0)
    estoque_atual = models.IntegerField("estoque atual", default=0)
    estoque_minimo = models.IntegerField("estoque minimo", default=0)
    ativo = models.BooleanField("ativo", default=True)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)

    class Meta:
        verbose_name = "produto"
        verbose_name_plural = "produtos"
        ordering = ["nome"]
        constraints = [
            models.UniqueConstraint(fields=["rede", "nome"], name="produto_unico_por_rede"),
        ]

    def __str__(self) -> str:
        return f"{self.nome} (R$ {self.preco_de_venda})"

    @property
    def abaixo_do_minimo(self) -> bool:
        return self.estoque_atual <= self.estoque_minimo

    @property
    def margem(self):
        if not self.preco_de_venda:
            return 0
        return round((self.preco_de_venda - self.custo) * 100 / self.preco_de_venda, 1)


class Venda(models.Model):
    class Situacao(models.TextChoices):
        ABERTA = "aberta", "Aberta"
        FINALIZADA = "finalizada", "Finalizada"
        CANCELADA = "cancelada", "Cancelada"

    class FormaDePagamento(models.TextChoices):
        DINHEIRO = "dinheiro", "Dinheiro"
        PIX = "pix", "Pix"
        CREDITO = "credito", "Cartao de credito"
        DEBITO = "debito", "Cartao de debito"
        FIADO = "fiado", "A prazo (fiado)"

    rede = models.ForeignKey(Rede, on_delete=models.CASCADE, related_name="vendas")
    unidade = models.ForeignKey(
        Unidade, on_delete=models.SET_NULL, null=True, blank=True, related_name="vendas"
    )
    aluno = models.ForeignKey(
        "usuarios.Usuario",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vendas",
        verbose_name="cliente",
    )
    situacao = models.CharField(
        "situacao", max_length=12, choices=Situacao.choices, default=Situacao.ABERTA
    )
    forma_de_pagamento = models.CharField(
        "forma de pagamento", max_length=10, choices=FormaDePagamento.choices, blank=True
    )
    desconto = models.DecimalField("desconto", max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField("total", max_digits=10, decimal_places=2, default=0)
    observacoes = models.CharField("observacoes", max_length=200, blank=True)
    criada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vendas_abertas",
    )
    criada_em = models.DateTimeField("criada em", auto_now_add=True)
    finalizada_em = models.DateTimeField("finalizada em", null=True, blank=True)

    class Meta:
        verbose_name = "venda"
        verbose_name_plural = "vendas"
        ordering = ["-criada_em"]
        indexes = [models.Index(fields=["rede", "situacao"])]

    def __str__(self) -> str:
        return f"Venda {self.pk or '(nova)'} — R$ {self.total} ({self.get_situacao_display()})"

    def recalcular(self, salvar: bool = True) -> Venda:
        subtotal = sum((item.subtotal for item in self.itens.all()), start=0)
        self.total = max(0, subtotal - (self.desconto or 0))
        if salvar:
            self.save(update_fields=["total"])
        return self


class ItemDaVenda(models.Model):
    venda = models.ForeignKey(Venda, on_delete=models.CASCADE, related_name="itens")
    produto = models.ForeignKey(Produto, on_delete=models.PROTECT, related_name="itens_de_venda")
    quantidade = models.PositiveIntegerField("quantidade", default=1)
    preco_unitario = models.DecimalField(
        "preco unitario (no momento da venda)", max_digits=10, decimal_places=2, default=0
    )
    subtotal = models.DecimalField("subtotal", max_digits=10, decimal_places=2, default=0)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)

    class Meta:
        verbose_name = "item da venda"
        verbose_name_plural = "itens da venda"
        ordering = ["pk"]

    def __str__(self) -> str:
        return f"{self.quantidade}x {self.produto.nome}"

    def calcular_subtotal(self, salvar: bool = True) -> ItemDaVenda:
        self.subtotal = (self.preco_unitario or 0) * (self.quantidade or 0)
        if salvar:
            self.save(update_fields=["subtotal"])
        return self


class MovimentoDeEstoque(models.Model):
    class Tipo(models.TextChoices):
        ENTRADA = "entrada", "Entrada"
        SAIDA = "saida", "Saida por venda"
        AJUSTE = "ajuste", "Ajuste de inventario"
        DEVOLUCAO = "devolucao", "Devolucao de venda"

    produto = models.ForeignKey(Produto, on_delete=models.CASCADE, related_name="movimentos")
    tipo = models.CharField("tipo", max_length=10, choices=Tipo.choices)
    quantidade = models.IntegerField("quantidade (positiva entrada, negativa saida)")
    saldo_apos = models.IntegerField("saldo apos o movimento", default=0)
    motivo = models.CharField("motivo", max_length=200, blank=True)
    venda = models.ForeignKey(
        Venda, on_delete=models.SET_NULL, null=True, blank=True, related_name="movimentos"
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="movimentos_de_estoque",
    )
    criado_em = models.DateTimeField("criado em", auto_now_add=True)

    class Meta:
        verbose_name = "movimento de estoque"
        verbose_name_plural = "movimentos de estoque"
        ordering = ["-criado_em"]

    def __str__(self) -> str:
        return f"{self.get_tipo_display()} de {self.quantidade} — {self.produto.nome}"
