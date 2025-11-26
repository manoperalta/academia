from django.contrib import admin
from .models import Plano, Pagamento

@admin.register(Plano)
class PlanoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'tipo', 'valor')
    search_fields = ('nome',)

@admin.register(Pagamento)
class PagamentoAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'plano', 'data_pagamento', 'data_inicio', 'data_fim', 'valor_pago')
    list_filter = ('plano', 'data_pagamento')
    search_fields = ('usuario__username', 'usuario__email')
