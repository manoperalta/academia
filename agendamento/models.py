from django.db import models
from django.conf import settings
from aulas.models import Aulas

class Painel(models.Model):
    criador = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="Criador (Professor/Admin)")
    data_painel = models.DateField(verbose_name="Data do Painel")
    horario_inicial_painel = models.TimeField(verbose_name="Horário Inicial")
    horario_final_painel = models.TimeField(verbose_name="Horário Final")
    numero_de_user = models.PositiveIntegerField(verbose_name="Capacidade de Alunos")
    # Aulas que compõem o painel (sequência de exercícios)
    aulas = models.ManyToManyField(Aulas, verbose_name="Aulas/Exercícios", related_name="paineis")
    
    data_create_painel = models.DateTimeField(auto_now_add=True, verbose_name="Data de Criação")
    data_at_painel = models.DateTimeField(auto_now=True, verbose_name="Última Atualização")

    def __str__(self):
        return f"Painel {self.id} - {self.data_painel} ({self.horario_inicial_painel} - {self.horario_final_painel})"

    class Meta:
        verbose_name = "Painel de Agendamento"
        verbose_name_plural = "Painéis de Agendamento"
        ordering = ['-data_painel', 'horario_inicial_painel']

class Agendamento(models.Model):
    STATUS_CHOICES = (
        ('Agendado', 'Agendado'),
        ('Cancelado', 'Cancelado'),
        ('Concluido', 'Concluído'),
    )
    
    painel = models.ForeignKey(Painel, on_delete=models.CASCADE, related_name='agendamentos', verbose_name="Painel")
    aluno = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='meus_agendamentos', verbose_name="Aluno")
    data_agendamento = models.DateTimeField(auto_now_add=True, verbose_name="Data do Agendamento")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Agendado', verbose_name="Status")

    def __str__(self):
        return f"Agendamento de {self.aluno} para {self.painel}"

    class Meta:
        verbose_name = "Agendamento"
        verbose_name_plural = "Agendamentos"
        unique_together = ('painel', 'aluno') # Evitar duplicidade de agendamento para o mesmo painel
