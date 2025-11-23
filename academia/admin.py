from django.contrib import admin
from .models import Configuracao, IdentidadeVisual

@admin.register(Configuracao)
class ConfiguracaoAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'cnpj', 'endereco')

@admin.register(IdentidadeVisual)
class IdentidadeVisualAdmin(admin.ModelAdmin):
    list_display = ('id', 'logotipo', 'favicon')
