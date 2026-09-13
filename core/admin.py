"""Admin restrito ao pessoal da plataforma (operacao usa o painel proprio)."""

from django.contrib import admin

from core.models import Rede, Unidade, VinculoUsuario


@admin.register(Rede)
class RedeAdmin(admin.ModelAdmin):
    list_display = ("nome", "slug", "status", "criado_em")
    list_filter = ("status",)
    search_fields = ("nome", "slug", "cnpj")
    prepopulated_fields = {"slug": ("nome",)}


@admin.register(Unidade)
class UnidadeAdmin(admin.ModelAdmin):
    list_display = ("nome", "rede", "tipo", "status", "cidade", "uf")
    list_filter = ("rede", "tipo", "status")
    search_fields = ("nome", "codigo", "cnpj")


@admin.register(VinculoUsuario)
class VinculoUsuarioAdmin(admin.ModelAdmin):
    list_display = ("usuario", "rede", "unidade", "papel", "ativo")
    list_filter = ("rede", "papel", "ativo")
    search_fields = ("usuario__username", "usuario__email")
