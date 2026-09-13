"""Django admin da plataforma: e por aqui que a SafeStack liga/desliga a compra de pacote.

O ponto de compra de pacote nasce **desabilitado** (requisito de produto) e o interruptor e
``ConfiguracaoPlataforma.permitir_compra_de_pacote``. A tela existe para o time comercial mudar
isso sem depender de deploy -- por isso o singleton aparece no admin sem poder ser criado nem
apagado por ali.
"""

from __future__ import annotations

from django.contrib import admin, messages

from plataforma.models import (
    Assinatura,
    ConfiguracaoPlataforma,
    EventoCobranca,
    Fatura,
    Impersonacao,
    Pacote,
)


@admin.register(ConfiguracaoPlataforma)
class ConfiguracaoPlataformaAdmin(admin.ModelAdmin):
    list_display = ("nome_emitente", "asaas_ambiente", "permitir_compra_de_pacote", "regua_ativa")
    fieldsets = (
        ("Emitente", {"fields": ("nome_emitente", "cnpj_emitente", "email_financeiro")}),
        (
            "Gateway",
            {"fields": ("asaas_api_key", "asaas_ambiente", "asaas_base_url", "token_webhook")},
        ),
        ("Cobranca", {"fields": ("trial_dias", "dias_bloqueio", "dias_suspensao")}),
        ("Regua", {"fields": ("multa_percentual", "juros_dia_percentual", "regua_ativa")}),
        (
            "Compra de pacote",
            {
                "fields": ("permitir_compra_de_pacote",),
                "description": (
                    "Desligado: o cadastro e a troca de pacote no painel nao oferecem compra. "
                    "Ligado: a compra aparece para o cliente."
                ),
            },
        ),
    )

    def has_add_permission(self, request):
        return not ConfiguracaoPlataforma.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        estado = "habilitada" if obj.permitir_compra_de_pacote else "desabilitada"
        messages.success(request, f"Configuracao salva. Compra de pacote {estado}.")


@admin.register(Pacote)
class PacoteAdmin(admin.ModelAdmin):
    list_display = (
        "nome",
        "codigo",
        "limite_alunos",
        "limite_professores",
        "limite_unidades",
        "limite_armazenamento_gb",
        "preco_mensal",
        "ativo",
    )
    list_filter = ("ativo", "visivel_no_site")
    search_fields = ("nome", "codigo")


@admin.register(Assinatura)
class AssinaturaAdmin(admin.ModelAdmin):
    list_display = (
        "rede",
        "pacote",
        "ciclo",
        "renovacao_em",
        "trial_termina_em",
        "cancelada_em",
    )
    list_filter = ("ciclo", "pacote")
    search_fields = ("rede__nome", "rede__slug")
    raw_id_fields = ("rede", "pacote", "pacote_agendado", "autorizado_por")


@admin.register(Fatura)
class FaturaAdmin(admin.ModelAdmin):
    list_display = ("numero", "rede", "vencimento", "valor_final", "status")
    list_filter = ("status",)
    search_fields = ("numero", "rede__nome")
    raw_id_fields = ("rede", "assinatura")


@admin.register(EventoCobranca)
class EventoCobrancaAdmin(admin.ModelAdmin):
    list_display = ("rede", "marco", "canal", "status", "criado_em")
    list_filter = ("marco", "canal", "status")


@admin.register(Impersonacao)
class ImpersonacaoAdmin(admin.ModelAdmin):
    list_display = ("rede", "usuario_plataforma", "inicio", "fim")
    search_fields = ("rede__nome", "usuario_plataforma__username")
