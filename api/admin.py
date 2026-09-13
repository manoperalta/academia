from django.contrib import admin

from api.models import ApiToken, RegistroAuditoria


@admin.register(ApiToken)
class ApiTokenAdmin(admin.ModelAdmin):
    list_display = ("nome", "prefixo", "rede", "unidade", "ativo", "ultimo_uso_em")
    list_filter = ("ativo", "rede")
    search_fields = ("nome", "prefixo")
    readonly_fields = ("prefixo", "hash_segredo", "ultimo_uso_em", "ultimo_ip", "criado_em")


@admin.register(RegistroAuditoria)
class RegistroAuditoriaAdmin(admin.ModelAdmin):
    list_display = ("criado_em", "acao", "entidade", "entidade_id", "rede", "usuario")
    list_filter = ("acao", "rede")
    search_fields = ("entidade", "entidade_id", "descricao")
    date_hierarchy = "criado_em"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
