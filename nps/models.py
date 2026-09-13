"""Pesquisas e NPS (item de paridade da fase 8)."""

from __future__ import annotations

from django.db import models


class TipoDePesquisa(models.TextChoices):
    NPS = "nps", "NPS (0 a 10)"
    NOTA = "nota", "Nota (1 a 5)"
    TEXTO = "texto", "Texto livre"


class Pesquisa(models.Model):
    """Pesquisa aplicada ao aluno (pos-aula, pos-atendimento, trimestral)."""

    rede = models.ForeignKey("core.Rede", on_delete=models.CASCADE, related_name="pesquisas")
    unidade = models.ForeignKey(
        "core.Unidade",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="pesquisas",
        verbose_name="unidade",
    )
    titulo = models.CharField("titulo", max_length=120)
    pergunta = models.CharField("pergunta", max_length=300)
    tipo = models.CharField(
        "tipo", max_length=8, choices=TipoDePesquisa.choices, default=TipoDePesquisa.NPS
    )
    ativa = models.BooleanField("ativa", default=True)
    inicio = models.DateField("inicio", null=True, blank=True)
    fim = models.DateField("fim", null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "pesquisa"
        verbose_name_plural = "pesquisas"
        ordering = ["-criado_em"]

    def __str__(self) -> str:
        return self.titulo

    def aceita_resposta(self, quando=None) -> bool:
        from django.utils import timezone

        quando = quando or timezone.localdate()
        if not self.ativa:
            return False
        if self.inicio and quando < self.inicio:
            return False
        return not (self.fim and quando > self.fim)


class Resposta(models.Model):
    """Resposta do aluno; a nota 0-6 e um detrator e pede acao da unidade."""

    pesquisa = models.ForeignKey(Pesquisa, on_delete=models.CASCADE, related_name="respostas")
    aluno = models.ForeignKey(
        "usuarios.Usuario",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="respostas_de_pesquisa",
        verbose_name="aluno",
    )
    unidade = models.ForeignKey(
        "core.Unidade",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="respostas_de_pesquisa",
        verbose_name="unidade",
    )
    nota = models.PositiveSmallIntegerField("nota", null=True, blank=True)
    comentario = models.TextField("comentario", blank=True)
    tratada_em = models.DateTimeField("tratada em", null=True, blank=True)
    tratada_por = models.ForeignKey(
        "accounts.CustomUser",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="respostas_tratadas",
        verbose_name="tratada por",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "resposta"
        verbose_name_plural = "respostas"
        ordering = ["-criado_em"]
        constraints = [
            models.UniqueConstraint(fields=["pesquisa", "aluno"], name="resposta_unica_por_aluno"),
        ]

    def __str__(self) -> str:
        return f"{self.pesquisa} · {self.nota}"

    @property
    def detrator(self) -> bool:
        return self.pesquisa.tipo == TipoDePesquisa.NPS and self.nota is not None and self.nota <= 6
