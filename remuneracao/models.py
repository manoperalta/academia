"""Regras de comissao, apuracao mensal e memoria de calculo (RF-RED-017 / RF-CMP-014)."""

from __future__ import annotations

from decimal import Decimal

from django.db import models

ZERO = Decimal("0.00")


class TipoDeComissao(models.TextChoices):
    POR_AULA = "por_aula", "Por aula dada"
    POR_ALUNO = "por_aluno", "Por aluno ativo"
    PERCENTUAL = "percentual", "Percentual do que a unidade recebeu"
    FIXO = "fixo", "Valor fixo no periodo"


class RegraDeComissao(models.Model):
    """Regra de remuneracao: do professor, da unidade ou geral da rede (nesta ordem)."""

    rede = models.ForeignKey(
        "core.Rede", on_delete=models.CASCADE, related_name="regras_de_comissao"
    )
    unidade = models.ForeignKey(
        "core.Unidade",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="regras_de_comissao",
        verbose_name="unidade",
    )
    professor = models.ForeignKey(
        "professores.Professor",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="regras_de_comissao",
        verbose_name="professor",
        help_text="Em branco = regra da unidade/rede.",
    )
    tipo = models.CharField("tipo", max_length=12, choices=TipoDeComissao.choices)
    valor = models.DecimalField(
        "valor por aula/aluno", max_digits=12, decimal_places=2, default=ZERO
    )
    percentual = models.DecimalField("percentual", max_digits=6, decimal_places=3, default=ZERO)
    piso_mensal = models.DecimalField("piso mensal", max_digits=12, decimal_places=2, default=ZERO)
    teto_mensal = models.DecimalField("teto mensal", max_digits=12, decimal_places=2, default=ZERO)
    inicio_vigencia = models.DateField("inicio da vigencia", null=True, blank=True)
    fim_vigencia = models.DateField("fim da vigencia", null=True, blank=True)
    ativo = models.BooleanField("ativa", default=True)
    descricao = models.CharField("descricao", max_length=160, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "regra de comissao"
        verbose_name_plural = "regras de comissao"
        ordering = ["rede", "unidade", "professor", "-criado_em"]

    def __str__(self) -> str:
        alvo = self.professor or self.unidade or self.rede
        return f"{alvo} · {self.get_tipo_display()}"

    def vale_em(self, referencia) -> bool:
        if not self.ativo:
            return False
        if self.inicio_vigencia and referencia < self.inicio_vigencia:
            return False
        return not (self.fim_vigencia and referencia > self.fim_vigencia)


class SituacaoDeApuracao(models.TextChoices):
    PREVISTO = "previsto", "Previsto"
    EMITIDO = "emitido", "Emitido"
    PAGO = "pago", "Pago"
    CANCELADO = "cancelado", "Cancelado"


class ApuracaoDeComissao(models.Model):
    """Comissao apurada por professor e unidade no periodo (com memoria de calculo)."""

    rede = models.ForeignKey("core.Rede", on_delete=models.CASCADE, related_name="apuracoes")
    unidade = models.ForeignKey(
        "core.Unidade",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="apuracoes",
        verbose_name="unidade",
    )
    professor = models.ForeignKey(
        "professores.Professor",
        on_delete=models.CASCADE,
        related_name="apuracoes",
        verbose_name="professor",
    )
    inicio = models.DateField("inicio do periodo")
    fim = models.DateField("fim do periodo")
    situacao = models.CharField(
        "situacao",
        max_length=10,
        choices=SituacaoDeApuracao.choices,
        default=SituacaoDeApuracao.PREVISTO,
    )
    base_de_calculo = models.DecimalField(
        "base de calculo", max_digits=12, decimal_places=2, default=ZERO
    )
    valor_devido = models.DecimalField(
        "valor devido", max_digits=12, decimal_places=2, default=ZERO
    )
    valor_pago = models.DecimalField("valor pago", max_digits=12, decimal_places=2, default=ZERO)
    piso_aplicado = models.BooleanField("piso aplicado", default=False)
    teto_aplicado = models.BooleanField("teto aplicado", default=False)
    memoria = models.JSONField("memoria de calculo", default=list, blank=True)
    hash_do_calculo = models.CharField("hash do calculo", max_length=64, blank=True)
    observacoes = models.TextField("observacoes", blank=True)
    emitido_em = models.DateTimeField("emitido em", null=True, blank=True)
    pago_em = models.DateTimeField("pago em", null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "apuracao de comissao"
        verbose_name_plural = "apuracoes de comissao"
        ordering = ["-inicio", "professor__nome"]
        constraints = [
            models.UniqueConstraint(
                fields=["professor", "unidade", "inicio", "fim"], name="apuracao_unica_por_periodo"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.professor} · {self.inicio:%m/%Y} · R$ {self.valor_devido}"

    @property
    def saldo(self) -> Decimal:
        return (self.valor_devido or ZERO) - (self.valor_pago or ZERO)

    @property
    def paga(self) -> bool:
        return self.situacao == SituacaoDeApuracao.PAGO

    @property
    def atrasada(self) -> bool:
        from django.utils import timezone

        return (
            self.situacao in {SituacaoDeApuracao.EMITIDO, SituacaoDeApuracao.PREVISTO}
            and self.saldo > ZERO
            and self.fim < timezone.localdate().replace(day=1)
        )


class ItemDeComissao(models.Model):
    """Linha do demonstrativo: e o que permite conferir o numero item a item."""

    apuracao = models.ForeignKey(ApuracaoDeComissao, on_delete=models.CASCADE, related_name="itens")
    ordem = models.PositiveSmallIntegerField("ordem", default=1)
    tipo = models.CharField("tipo", max_length=20)
    descricao = models.CharField("descricao", max_length=200)
    base = models.DecimalField("base", max_digits=12, decimal_places=2, default=ZERO)
    percentual = models.DecimalField("percentual", max_digits=6, decimal_places=3, default=ZERO)
    valor = models.DecimalField("valor", max_digits=12, decimal_places=2, default=ZERO)

    class Meta:
        verbose_name = "item da comissao"
        verbose_name_plural = "itens da comissao"
        ordering = ["apuracao", "ordem"]

    def __str__(self) -> str:
        return f"{self.ordem}. {self.descricao}"
