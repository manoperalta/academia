from django.contrib import admin
from .models import Aulas, ImagemAula

class ImagemAulaInline(admin.TabularInline):
    model = ImagemAula
    extra = 1
    max_num = 5

@admin.register(Aulas)
class AulasAdmin(admin.ModelAdmin):
    list_display = ('nome', 'professor', 'categorias_exercicios', 'restricao', 'data_create_aula')
    list_filter = ('categorias_exercicios', 'restricao', 'data_create_aula', 'professor')
    search_fields = ('nome', 'descricao')
    inlines = [ImagemAulaInline]
