"""Modelos fiscais: configuracao do emissor e a nota de servico da mensalidade.

O sistema **calcula e guarda** a conta da nota (base, aliquota, ISS, retencoes) e emite em modo
simulado enquanto nao houver provedor configurado — a mesma escolha do gateway da fase 3, para nao
inventar nota fiscal de cliente sem autorizacao do fisco.
"""

from __future__ import annotations

from django.db import models

from core.models import Rede, Unidade


class ConfiguracaoFiscal(models.Model):
    """Como a rede emite nota: regime, municipio, aliquota e provedor."""

    class Regime(models.TextChoices):
        MEI = "mei", "MEI"
        SIMPLES = "simples", "Simples Nacional"
        PRESUMIDO = "presumido", "Lucro Presumido"
        REAL = "real", "Lucro Real"

    class Provedor(models.TextChoices):
        SIMULADO = "simulado", "Simulado (sem emissao real)"
        NACIONAL = "nacional", "Emissor Nacional"
        MUNICIPAL = "municipal", "Emissor do municipio"

    rede = models.OneToOneField(Rede, on_delete=models.CASCADE, related_name="configuracao_fiscal")
    regime = models.CharField(
        "regime tributario", max_length=12, choices=Regime.choices, default=Regime.SIMPLES
    )
    municipio = models.CharField("municipio", max_length=100, blank=True)
    inscricao_municipal = models.CharField("inscricao municipal", max_length=40, blank=True)
    codigo_do_servico = models.CharField(
        "codigo do servico (LC 116)",
        max_length=10,
        default="6.01",
        help_text="6.01 = educacao fisica, academia e esporte.",
    )
    aliquota_iss = models.DecimalField(
        "aliquota de ISS (%)", max_digits=5, decimal_places=2, default=0
    )
    retem_pis_cofins_csll = models.BooleanField("reter PIS/COFINS/CSLL", default=False)
    retem_ir = models.BooleanField("reter IR", default=False)
    retem_inss = models.BooleanField("reter INSS", default=False)
    provedor = models.CharField(
        "provedor de emissao", max_length=12, choices=Provedor.choices, default=Provedor.SIMULADO
    )
    ambiente = models.CharField("ambiente", max_length=12, default="homologacao")
    token = models.CharField("token do provedor", max_length=200, blank=True)
    emissao_automatica = models.BooleanField("emitir automaticamente ao receber", default=False)
    serie = models.CharField("serie", max_length=5, default="1")
    atualizada_em = models.DateTimeField("atualizada em", auto_now=True)

    class Meta:
        verbose_name = "configuracao fiscal"
        verbose_name_plural = "configuracoes fiscais"

    def __str__(self) -> str:
        return f"Fiscal de {self.rede}"


class NotaFiscal(models.Model):
    """A nota de servico de um pagamento, com a memoria de calculo dos tributos."""

    class Situacao(models.TextChoices):
        PENDENTE = "pendente", "Pendente"
        EMITIDA = "emitida", "Emitida"
        CANCELADA = "cancelada", "Cancelada"
        ERRO = "erro", "Erro na emissao"

    rede = models.ForeignKey(Rede, on_delete=models.CASCADE, related_name="notas_fiscais")
    unidade = models.ForeignKey(
        Unidade, on_delete=models.SET_NULL, null=True, blank=True, related_name="notas_fiscais"
    )
    aluno = models.ForeignKey(
        "usuarios.Usuario",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notas_fiscais",
        verbose_name="tomador",
    )
    pagamento = models.ForeignKey(
        "financeiro.Pagamento",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notas_fiscais",
    )
    competencia = models.DateField("competencia")
    descricao_do_servico = models.CharField(
        "descricao do servico", max_length=250, default="Mensalidade de atividade fisica"
    )
    codigo_do_servico = models.CharField("codigo do servico", max_length=10, default="6.01")
    valor_do_servico = models.DecimalField(
        "valor do servico", max_digits=12, decimal_places=2, default=0
    )
    base_de_calculo = models.DecimalField(
        "base de calculo", max_digits=12, decimal_places=2, default=0
    )
    aliquota_iss = models.DecimalField(
        "aliquota de ISS (%)", max_digits=5, decimal_places=2, default=0
    )
    valor_do_iss = models.DecimalField("ISS", max_digits=12, decimal_places=2, default=0)
    retencoes = models.JSONField("retencoes", default=dict, blank=True)
    valor_liquido = models.DecimalField("valor liquido", max_digits=12, decimal_places=2, default=0)
    situacao = models.CharField(
        "situacao", max_length=10, choices=Situacao.choices, default=Situacao.PENDENTE
    )
    numero = models.CharField("numero da nota", max_length=20, blank=True)
    serie = models.CharField("serie", max_length=5, blank=True)
    codigo_de_verificacao = models.CharField("codigo de verificacao", max_length=64, blank=True)
    provedor = models.CharField("provedor", max_length=12, blank=True)
    resposta_do_provedor = models.JSONField("resposta do provedor", default=dict, blank=True)
    emitida_em = models.DateTimeField("emitida em", null=True, blank=True)
    cancelada_em = models.DateTimeField("cancelada em", null=True, blank=True)
    motivo_do_cancelamento = models.CharField("motivo do cancelamento", max_length=200, blank=True)
    criada_em = models.DateTimeField("criada em", auto_now_add=True)

    class Meta:
        verbose_name = "nota fiscal"
        verbose_name_plural = "notas fiscais"
        ordering = ["-competencia", "-numero"]
        constraints = [
            models.UniqueConstraint(fields=["pagamento"], name="uma_nota_por_pagamento"),
        ]
        indexes = [models.Index(fields=["rede", "situacao"])]

    def __str__(self) -> str:
        return f"NF {self.numero or '(sem numero)'} — R$ {self.valor_do_servico}"

    @property
    def total_retencoes(self):
        from decimal import Decimal

        return sum((Decimal(str(valor)) for valor in (self.retencoes or {}).values()), Decimal("0"))

    @property
    def esta_emitida(self) -> bool:
        return self.situacao == self.Situacao.EMITIDA


class EventoFiscal(models.Model):
    """Historico da nota: criada, emitida, erro, cancelada."""

    class Tipo(models.TextChoices):
        CRIADA = "criada", "Nota criada"
        EMITIDA = "emitida", "Emitida"
        ERRO = "erro", "Erro"
        CANCELADA = "cancelada", "Cancelada"

    nota = models.ForeignKey(NotaFiscal, on_delete=models.CASCADE, related_name="eventos")
    tipo = models.CharField("tipo", max_length=10, choices=Tipo.choices)
    detalhe = models.TextField("detalhe", blank=True)
    dados = models.JSONField("dados", default=dict, blank=True)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)

    class Meta:
        verbose_name = "evento fiscal"
        verbose_name_plural = "eventos fiscais"
        ordering = ["-criado_em"]

    def __str__(self) -> str:
        return f"{self.get_tipo_display()} — nota {self.nota_id}"
