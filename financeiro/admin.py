from django.contrib import admin
from .models import Plano, Pagamento, GatewayConfig

@admin.register(GatewayConfig)
class GatewayConfigAdmin(admin.ModelAdmin):
    list_display = ('nome', 'ambiente', 'ativo')
    fieldsets = (
        ('Configuração Geral', {
            'fields': ('ativo', 'ambiente')
        }),
        ('Credenciais', {
            'fields': ('token', 'public_key'),
            'description': 'Obtenha estas credenciais no painel do desenvolvedor do PagBank.'
        }),
        ('Webhooks', {
            'fields': ('url_webhook',),
            'description': 'Configure esta URL no painel do PagBank para receber atualizações automáticas.'
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
