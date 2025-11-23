from django.contrib import admin
from .models import Usuario

@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    list_display = ('nome', 'cpf_cnpj_user', 'status_user', 'data_create_user')
    list_filter = ('status_user', 'data_create_user')
    search_fields = ('nome', 'cpf_cnpj_user')
