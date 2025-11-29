from django.db import models
from django.conf import settings
from datetime import timedelta
from dateutil.relativedelta import relativedelta
from django.core.exceptions import ValidationError

class GatewayConfig(models.Model):
    AMBIENTE_CHOICES = [
        ('sandbox', 'Sandbox (Testes)'),
        ('producao', 'Produção'),
    ]

    nome = models.CharField(max_length=50, default="PagBank", editable=False)
    ativo = models.BooleanField(default=True, verbose_name="Gateway Ativo")
    ambiente = models.CharField(max_length=20, choices=AMBIENTE_CHOICES, default='sandbox', verbose_name="Ambiente")
    
    # Credenciais
    token = models.CharField(max_length=255, verbose_name="Token de Acesso")
    public_key = models.TextField(verbose_name="Chave Pública (Public Key)", blank=True, null=True)
    
    # Configurações adicionais
    url_webhook = models.URLField(verbose_name="URL de Notificação (Webhook)", blank=True, null=True, help_text="URL para receber atualizações de status")
    
    def save(self, *args, **kwargs):
        if not self.pk and GatewayConfig.objects.exists():
            raise ValidationError('Apenas uma configuração de Gateway é permitida.')
        return super(GatewayConfig, self).save(*args, **kwargs)

    def __str__(self):
        return f"Configuração PagBank ({self.get_ambiente_display()})"

    class Meta:
        verbose_name = "Configuração do Gateway (PagBank)"
        verbose_name_plural = "Configuração do Gateway (PagBank)"

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
    STATUS_CHOICES = [
        ('pendente', 'Pendente'),
        ('pago', 'Pago'),
        ('cancelado', 'Cancelado'),
        ('em_analise', 'Em Análise'),
        ('devolvido', 'Devolvido'),
    ]

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="Usuário", related_name='pagamentos')
    plano = models.ForeignKey(Plano, on_delete=models.SET_NULL, null=True, verbose_name="Plano")
    data_pagamento = models.DateField(auto_now_add=True, verbose_name="Data de Criação")
    valor_pago = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Valor")
    
    # Vigência
    data_inicio = models.DateField(verbose_name="Início da Vigência")
    data_fim = models.DateField(verbose_name="Fim da Vigência", blank=True)

    # Campos do Gateway
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pendente', verbose_name="Status do Pagamento")
    transaction_id = models.CharField(max_length=100, blank=True, null=True, verbose_name="ID da Transação (Gateway)")
    link_pagamento = models.URLField(blank=True, null=True, verbose_name="Link de Pagamento")
    qr_code_base64 = models.TextField(blank=True, null=True, verbose_name="QR Code (Pix)")
    qr_code_text = models.TextField(blank=True, null=True, verbose_name="Código Pix (Copia e Cola)")

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
        return f"{self.usuario} - {self.plano} ({self.get_status_display()})"

    class Meta:
        verbose_name = "Pagamento"
        verbose_name_plural = "Pagamentos"
        ordering = ['-data_pagamento']
