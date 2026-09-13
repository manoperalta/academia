"""Pontos, conquistas e ranking do aluno (item de paridade da fase 8)."""

from __future__ import annotations

from django.db import models


class EventoDePontos(models.TextChoices):
    CHECKIN = "checkin", "Check-in na academia"
    AULA = "aula", "Aula concluida"
    AVALIACAO = "avaliacao", "Avaliacao fisica"
    INDICACAO = "indicacao", "Indicacao de amigo"
    NPS = "nps", "Resposta de pesquisa"
    PAGAMENTO_EM_DIA = "pagamento_em_dia", "Mes pago em dia"


class RegraDePontos(models.Model):
    """Quanto cada evento vale (por rede)."""

    rede = models.ForeignKey("core.Rede", on_delete=models.CASCADE, related_name="regras_de_pontos")
    evento = models.CharField("evento", max_length=20, choices=EventoDePontos.choices)
    pontos = models.PositiveIntegerField("pontos", default=10)
    limite_diario = models.PositiveSmallIntegerField(
        "limite por dia", default=1, help_text="0 = sem limite"
    )
    ativo = models.BooleanField("ativa", default=True)

    class Meta:
        verbose_name = "regra de pontos"
        verbose_name_plural = "regras de pontos"
        constraints = [
            models.UniqueConstraint(fields=["rede", "evento"], name="regra_de_pontos_unica")
        ]
        ordering = ["rede", "evento"]

    def __str__(self) -> str:
        return f"{self.get_evento_display()} = {self.pontos} ponto(s)"


class SaldoDePontos(models.Model):
    """Posicao atual do aluno (uma linha por aluno)."""

    rede = models.ForeignKey("core.Rede", on_delete=models.CASCADE, related_name="saldos_de_pontos")
    aluno = models.OneToOneField(
        "usuarios.Usuario",
        on_delete=models.CASCADE,
        related_name="saldo_de_pontos",
        verbose_name="aluno",
    )
    pontos = models.PositiveIntegerField("pontos", default=0)
    nivel = models.PositiveSmallIntegerField("nivel", default=1)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "saldo de pontos"
        verbose_name_plural = "saldos de pontos"
        ordering = ["-pontos"]

    def __str__(self) -> str:
        return f"{self.aluno} · {self.pontos} ponto(s) · nivel {self.nivel}"


class LancamentoDePontos(models.Model):
    """Extrato de pontos (cada ganho fica registrado)."""

    saldo = models.ForeignKey(SaldoDePontos, on_delete=models.CASCADE, related_name="lancamentos")
    evento = models.CharField("evento", max_length=20, choices=EventoDePontos.choices)
    pontos = models.IntegerField("pontos")
    referencia = models.CharField("referencia", max_length=80, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "lancamento de pontos"
        verbose_name_plural = "lancamentos de pontos"
        ordering = ["-criado_em"]
        constraints = [
            models.UniqueConstraint(
                fields=["saldo", "evento", "referencia"], name="lancamento_unico_por_referencia"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.get_evento_display()} ({self.pontos:+d})"


class Conquista(models.Model):
    """Regra de conquista: N eventos do mesmo tipo liberam o selo."""

    rede = models.ForeignKey("core.Rede", on_delete=models.CASCADE, related_name="conquistas")
    nome = models.CharField("nome", max_length=80)
    descricao = models.CharField("descricao", max_length=200, blank=True)
    evento = models.CharField("evento", max_length=20, choices=EventoDePontos.choices)
    quantidade = models.PositiveSmallIntegerField("quantidade necessaria", default=10)
    pontos_bonus = models.PositiveIntegerField("pontos de bonus", default=0)
    icone = models.CharField("icone", max_length=8, blank=True)
    ativa = models.BooleanField("ativa", default=True)

    class Meta:
        verbose_name = "conquista"
        verbose_name_plural = "conquistas"
        ordering = ["rede", "evento", "quantidade"]

    def __str__(self) -> str:
        return f"{self.nome} ({self.quantidade}x {self.get_evento_display()})"


class ConquistaDoAluno(models.Model):
    """Selo conquistado (uma vez por aluno)."""

    aluno = models.ForeignKey(
        "usuarios.Usuario",
        on_delete=models.CASCADE,
        related_name="conquistas_do_aluno",
        verbose_name="aluno",
    )
    conquista = models.ForeignKey(Conquista, on_delete=models.CASCADE, related_name="ganhadores")
    conquistada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "conquista do aluno"
        verbose_name_plural = "conquistas do aluno"
        ordering = ["-conquistada_em"]
        constraints = [
            models.UniqueConstraint(
                fields=["aluno", "conquista"], name="conquista_unica_por_aluno"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.aluno} · {self.conquista.nome}"
