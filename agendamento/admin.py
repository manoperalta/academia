from django.contrib import admin
from .models import Painel, Agendamento

@admin.register(Painel)
class PainelAdmin(admin.ModelAdmin):
    list_display = ('data_painel', 'horario_inicial_painel', 'horario_final_painel', 'criador', 'numero_de_user')
    list_filter = ('data_painel', 'criador')
    search_fields = ('criador__username', 'criador__first_name')
    filter_horizontal = ('aulas',) # Facilita a seleção de múltiplas aulas

@admin.register(Agendamento)
class AgendamentoAdmin(admin.ModelAdmin):
    list_display = ('aluno', 'painel', 'status', 'data_agendamento')
    list_filter = ('status', 'data_agendamento')
    search_fields = ('aluno__username', 'aluno__first_name')
