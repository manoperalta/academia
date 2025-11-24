from django.db import models
from django.conf import settings
from aulas.models import Aulas

class Painel(models.Model):
    aula = models.ForeignKey(Aulas, on_delete=models.CASCADE, verbose_name="Aula")
    data = models.DateField(verbose_name="Data")
    hora_inicio = models.TimeField(verbose_name="Hora de Início")
    hora_fim = models.TimeField(verbose_name="Hora de Fim")
    responsavel = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="Responsável", related_name='paineis_criados')
    
    data_create = models.DateTimeField(auto_now_add=True, verbose_name="Data de Criação")
    data_update = models.DateTimeField(auto_now=True, verbose_name="Última Atualização")

    def __str__(self):
        return f"{self.aula.nome} - {self.data} ({self.hora_inicio} - {self.hora_fim})"

    class Meta:
        verbose_name = "Painel de Aula"
        verbose_name_plural = "Painéis de Aulas"
        ordering = ['-data', '-hora_inicio']
