from django.contrib import admin
from .models import Plano, Pagamento, GatewayConfig, Despesa

@admin.register(GatewayConfig)
class GatewayConfigAdmin(admin.ModelAdmin):
    list_display = ('gateway', 'ambiente', 'ativo')
    fieldsets = (
        ('Configuração Geral', {
            'fields': ('gateway', 'ativo', 'ambiente')
        }),
        ('Credenciais', {
            'fields': ('access_token', 'public_key'),
            'description': 'Obtenha estas credenciais no painel do desenvolvedor do gateway selecionado.'
        }),
        ('Webhooks', {
            'fields': ('url_webhook',),
            'description': 'Configure esta URL no painel do gateway para receber atualizações automáticas.'
        }),
    )

    def has_add_permission(self, request):
        # Impede criar mais de uma configuração se já existir uma
        if GatewayConfig.objects.exists():
            return False
        return True

@admin.register(Plano)
class PlanoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'tipo', 'valor')
    search_fields = ('nome',)

@admin.register(Pagamento)
class PagamentoAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'plano', 'valor_pago', 'status', 'data_inicio', 'data_fim')
    list_filter = ('status', 'plano', 'data_pagamento')
    search_fields = ('usuario__username', 'usuario__email', 'transaction_id')
    readonly_fields = ('transaction_id', 'link_pagamento', 'qr_code_text', 'qr_code_base64')
    
    fieldsets = (
        ('Informações do Pagamento', {
            'fields': ('usuario', 'plano', 'valor_pago', 'status')
        }),
        ('Vigência', {
            'fields': ('data_inicio', 'data_fim')
        }),
        ('Integração Gateway', {
            'fields': ('transaction_id', 'link_pagamento', 'qr_code_text'),
            'classes': ('collapse',)
        }),
    )

@admin.register(Despesa)
class DespesaAdmin(admin.ModelAdmin):
    list_display = ('descricao', 'valor', 'data', 'categoria')
    list_filter = ('data', 'categoria')
    search_fields = ('descricao', 'categoria')
