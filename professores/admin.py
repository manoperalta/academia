from django.contrib import admin
from .models import Professor

@admin.register(Professor)
class ProfessorAdmin(admin.ModelAdmin):
    list_display = ('nome', 'cpf_cnpj_prof', 'status_prof', 'data_create_prof')
    list_filter = ('status_prof', 'data_create_prof')
    search_fields = ('nome', 'cpf_cnpj_prof')
