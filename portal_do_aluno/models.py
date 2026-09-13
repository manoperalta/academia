"""Modelos do portal do aluno: lista de espera e preferencias de aviso.

Agendar e cancelar usam o ``agendamento.Agendamento`` que ja existe; aqui ficam so as duas coisas que
faltavam: a **fila de espera** de turma cheia e as **preferencias de notificacao** do aluno.
"""

from __future__ import annotations

from django.db import models

from painel.models import Painel
from usuarios.models import Usuario


class ListaDeEspera(models.Model):
    """Fila de espera de uma turma cheia — quem entrou primeiro e chamado primeiro."""

    turma = models.ForeignKey(Painel, on_delete=models.CASCADE, related_name="lista_de_espera")
    aluno = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name="esperas")
    avisado = models.BooleanField("avisado sobre a vaga", default=False)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)

    class Meta:
        verbose_name = "entrada na lista de espera"
        verbose_name_plural = "entradas na lista de espera"
        ordering = ["criado_em"]
        constraints = [
            models.UniqueConstraint(
                fields=["turma", "aluno"], name="espera_unica_por_aluno_e_turma"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.aluno} esperando em {self.turma}"


class PreferenciaDeNotificacao(models.Model):
    """O que o aluno quer receber — e por onde."""

    class Canal(models.TextChoices):
        WHATSAPP = "whatsapp", "WhatsApp"
        EMAIL = "email", "E-mail"
        NENHUM = "nenhum", "Nao quero receber"

    aluno = models.OneToOneField(Usuario, on_delete=models.CASCADE, related_name="preferencias")
    canal = models.CharField("canal", max_length=10, choices=Canal.choices, default=Canal.WHATSAPP)
    avisar_vencimento = models.BooleanField("avisar sobre vencimento", default=True)
    avisar_aula = models.BooleanField("avisar na vespera da aula", default=True)
    avisar_aniversario = models.BooleanField("avisar aniversario", default=False)
    receber_novidades = models.BooleanField("receber novidades da academia", default=False)
    atualizado_em = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        verbose_name = "preferencia de notificacao"
        verbose_name_plural = "preferencias de notificacao"

    def __str__(self) -> str:
        return f"Preferencias de {self.aluno}"
