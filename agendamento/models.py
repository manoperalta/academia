from django.conf import settings
from django.db import models

from core.models import TenantModel
from painel.models import Painel  # Importando o modelo correto

# Modelo Painel removido pois agora usamos o do app 'painel'


class Agendamento(TenantModel):
    STATUS_CHOICES = (
        ("Agendado", "Agendado"),
        ("Faltou", "Faltou (aluno ausente)"),
        ("Cancelado", "Cancelado"),
        ("Concluido", "Concluído"),
    )

    painel = models.ForeignKey(
        Painel, on_delete=models.CASCADE, related_name="agendamentos", verbose_name="Painel"
    )
    aluno = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="meus_agendamentos",
        verbose_name="Aluno",
    )
    data_agendamento = models.DateTimeField(auto_now_add=True, verbose_name="Data do Agendamento")
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="Agendado", verbose_name="Status"
    )

    def __str__(self):
        return f"Agendamento de {self.aluno} para {self.painel}"

    class Meta:
        verbose_name = "Agendamento"
        verbose_name_plural = "Agendamentos"
        unique_together = (
            "painel",
            "aluno",
        )  # Evitar duplicidade de agendamento para o mesmo painel
