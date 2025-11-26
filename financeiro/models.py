from django.db import models
from django.conf import settings
from datetime import timedelta
from dateutil.relativedelta import relativedelta

class Plano(models.Model):
    TIPOS_PLANO = [
        ('semanal', 'Semanal'),
        ('mensal', 'Mensal'),
        ('semestral', 'Semestral'),
        ('anual', 'Anual'),
    ]

    nome = models.CharField(max_length=100, verbose_name="Nome do Plano")
    tipo = models.CharField(max_length=20, choices=TIPOS_PLANO, verbose_name="Periodicidade")
    valor = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Valor")
    descricao = models.TextField(blank=True, verbose_name="Descrição")

    def __str__(self):
        return f"{self.nome} - R$ {self.valor}"

    class Meta:
        verbose_name = "Plano"
        verbose_name_plural = "Planos"

class Pagamento(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="Usuário", related_name='pagamentos')
    plano = models.ForeignKey(Plano, on_delete=models.SET_NULL, null=True, verbose_name="Plano")
    data_pagamento = models.DateField(auto_now_add=True, verbose_name="Data do Pagamento")
    valor_pago = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Valor Pago")
    
    # Vigência
    data_inicio = models.DateField(verbose_name="Início da Vigência")
    data_fim = models.DateField(verbose_name="Fim da Vigência", blank=True)

    def save(self, *args, **kwargs):
        if not self.data_fim and self.plano and self.data_inicio:
            if self.plano.tipo == 'semanal':
                self.data_fim = self.data_inicio + timedelta(weeks=1)
            elif self.plano.tipo == 'mensal':
                self.data_fim = self.data_inicio + relativedelta(months=1)
            elif self.plano.tipo == 'semestral':
                self.data_fim = self.data_inicio + relativedelta(months=6)
            elif self.plano.tipo == 'anual':
                self.data_fim = self.data_inicio + relativedelta(years=1)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.usuario} - {self.plano} ({self.data_inicio} a {self.data_fim})"

    class Meta:
        verbose_name = "Pagamento"
        verbose_name_plural = "Pagamentos"
        ordering = ['-data_fim']
