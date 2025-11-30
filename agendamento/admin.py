from django.contrib import admin
from .models import Agendamento

# Painel agora é gerenciado pelo app 'painel'

@admin.register(Agendamento)
class AgendamentoAdmin(admin.ModelAdmin):
    list_display = ('aluno', 'painel', 'status', 'data_agendamento')
    list_filter = ('status', 'data_agendamento')
    search_fields = ('aluno__username', 'aluno__first_name')
