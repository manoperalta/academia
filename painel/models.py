from django.db import models
from django.conf import settings
from aulas.models import Aulas

class Painel(models.Model):
    nome = models.CharField(max_length=200, verbose_name="Nome do Painel", default="Painel de Aulas")
    data = models.DateField(verbose_name="Data")
    hora_inicio = models.TimeField(verbose_name="Hora de Início")
    hora_fim = models.TimeField(verbose_name="Hora de Fim")
    responsavel = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="Responsável", related_name='paineis_criados')
    numero_de_user = models.PositiveIntegerField(verbose_name="Capacidade de Alunos", null=True, blank=True, help_text="Deixe em branco para sem limite")
    
    data_create = models.DateTimeField(auto_now_add=True, verbose_name="Data de Criação")
    data_update = models.DateTimeField(auto_now=True, verbose_name="Última Atualização")

    def __str__(self):
        return f"{self.nome} - {self.data}"

    class Meta:
        verbose_name = "Painel de Aula"
        verbose_name_plural = "Painéis de Aulas"
        ordering = ['-data', '-hora_inicio']

class PainelItem(models.Model):
    painel = models.ForeignKey(Painel, on_delete=models.CASCADE, related_name='itens')
    aula = models.ForeignKey(Aulas, on_delete=models.CASCADE, verbose_name="Aula")
    ordem = models.PositiveIntegerField(default=0, verbose_name="Ordem")

    class Meta:
        ordering = ['ordem']
        verbose_name = "Item do Painel"
        verbose_name_plural = "Itens do Painel"
