"""Check-in do aluno pelo PWA (RF-RED-003: aluno treina em qualquer unidade da rede)."""

from __future__ import annotations

from django.db import models


class OrigemDoCheckin(models.TextChoices):
    PWA = "pwa", "Aplicativo do aluno"
    TOTEM = "totem", "Totem da recepcao"
    CATRACA = "catraca", "Catraca"
    MANUAL = "manual", "Lancado pela equipe"


class CheckinDoAluno(models.Model):
    """Registro de entrada; pontua na gamificacao quando confirmado."""

    rede = models.ForeignKey("core.Rede", on_delete=models.CASCADE, related_name="checkins")
    aluno = models.ForeignKey(
        "usuarios.Usuario", on_delete=models.CASCADE, related_name="checkins", verbose_name="aluno"
    )
    unidade = models.ForeignKey(
        "core.Unidade", on_delete=models.CASCADE, related_name="checkins", verbose_name="unidade"
    )
    origem = models.CharField(
        "origem", max_length=10, choices=OrigemDoCheckin.choices, default=OrigemDoCheckin.PWA
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "check-in"
        verbose_name_plural = "check-ins"
        ordering = ["-criado_em"]

    def __str__(self) -> str:
        return f"{self.aluno} em {self.unidade} ({self.get_origem_display()})"
