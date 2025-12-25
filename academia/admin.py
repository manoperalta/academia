from django.contrib import admin
from .models import Configuracao, IdentidadeVisual

@admin.register(Configuracao)
class ConfiguracaoAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'cnpj', 'endereco', 'theme_mode')
    list_editable = ('theme_mode',)
    fieldsets = (
        ('Informações Gerais', {
            'fields': ('titulo', 'endereco', 'numero', 'cep', 'cnpj', 'ie')
        }),
        ('Aparência', {
            'fields': ('theme_mode',),
            'description': 'Configure o tema visual do sistema'
        }),
        ('Alertas Financeiros', {
            'fields': ('dias_alerta_vencimento', 'mensagem_pagamento_atrasado'),
            'classes': ('collapse',)
        }),
        ('Mensagens de Aniversário', {
            'fields': ('mensagem_aniversario',),
            'classes': ('collapse',)
        }),
    )

@admin.register(IdentidadeVisual)
class IdentidadeVisualAdmin(admin.ModelAdmin):
    list_display = ('id', 'logotipo', 'favicon')
