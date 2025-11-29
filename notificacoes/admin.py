from django.contrib import admin
from .models import ConfiguracaoEmail, Notificacao

@admin.register(ConfiguracaoEmail)
class ConfiguracaoEmailAdmin(admin.ModelAdmin):
    list_display = ('host', 'username', 'remetente_email', 'ativo')
    fieldsets = (
        ('Servidor SMTP', {
            'fields': ('host', 'port', 'use_tls', 'use_ssl')
        }),
        ('Autenticação', {
            'fields': ('username', 'password')
        }),
        ('Remetente', {
            'fields': ('remetente_nome', 'remetente_email', 'ativo')
        }),
    )

    def has_add_permission(self, request):
        if ConfiguracaoEmail.objects.exists():
            return False
        return True

@admin.register(Notificacao)
class NotificacaoAdmin(admin.ModelAdmin):
    list_display = ('assunto', 'criado_por', 'data_criacao', 'status', 'data_envio')
    list_filter = ('status', 'data_criacao')
    search_fields = ('assunto', 'mensagem', 'destinatarios')
    readonly_fields = ('data_criacao', 'data_envio', 'erro_log')
    
    actions = ['enviar_notificacoes']

    def enviar_notificacoes(self, request, queryset):
        enviados = 0
        falhas = 0
        for notificacao in queryset:
            if notificacao.status != 'enviado':
                if notificacao.enviar():
                    enviados += 1
                else:
                    falhas += 1
        
        self.message_user(request, f"{enviados} notificações enviadas com sucesso. {falhas} falhas.")
    enviar_notificacoes.short_description = "Enviar notificações selecionadas"
