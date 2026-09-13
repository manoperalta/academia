"""Formularios do painel da plataforma."""

from __future__ import annotations

from django import forms

from plataforma.models import (
    Ciclo,
    ConfiguracaoPlataforma,
    ModuloPacote,
    Pacote,
)


class EstiloMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            if isinstance(campo.widget, forms.CheckboxInput):
                campo.widget.attrs["class"] = "h-4 w-4 rounded border-slate-300 text-emerald-600"
            elif isinstance(campo.widget, forms.CheckboxSelectMultiple):
                campo.widget.attrs["class"] = "space-y-1 text-sm"
            else:
                campo.widget.attrs["class"] = (
                    "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm "
                    "text-slate-800 shadow-sm focus:border-emerald-500 focus:outline-none"
                )


def _campo_modulos():
    return forms.MultipleChoiceField(
        choices=ModuloPacote.choices,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Modulos incluidos neste pacote",
    )


class PacoteForm(EstiloMixin, forms.ModelForm):
    modulos = _campo_modulos()

    class Meta:
        model = Pacote
        fields = [
            "nome",
            "codigo",
            "descricao",
            "limite_alunos",
            "limite_professores",
            "limite_unidades",
            "preco_mensal",
            "preco_anual",
            "modulos",
            "ordem_exibicao",
            "visivel_no_site",
            "ativo",
        ]

    def clean_modulos(self):
        return list(self.cleaned_data.get("modulos") or [])


class TenantForm(EstiloMixin, forms.Form):
    """Criacao manual de tenant (venda assistida, RF-PLT-002)."""

    nome = forms.CharField(max_length=150, label="Nome da academia")
    slug = forms.SlugField(max_length=60, label="Identificador na URL")
    pacote = forms.ModelChoiceField(queryset=Pacote.objects.filter(ativo=True), label="Pacote")
    ciclo = forms.ChoiceField(choices=Ciclo.choices, initial=Ciclo.MENSAL, label="Ciclo")
    cnpj = forms.CharField(max_length=20, required=False, label="CNPJ")
    email = forms.EmailField(required=False, label="E-mail do responsavel")
    telefone = forms.CharField(max_length=20, required=False, label="Telefone")
    dominio = forms.CharField(max_length=253, required=False, label="Dominio proprio")
    trial = forms.BooleanField(required=False, initial=True, label="Iniciar em periodo de teste")
    dono_email = forms.EmailField(
        required=False,
        label="E-mail do dono inicial",
        help_text="Cria o vinculo de administrador da rede para este e-mail (se a conta existir).",
    )


class TenantEdicaoForm(EstiloMixin, forms.Form):
    """Dados cadastrais + excecao comercial (RF-PLT-003)."""

    nome = forms.CharField(max_length=150)
    cnpj = forms.CharField(max_length=20, required=False)
    email_responsavel = forms.EmailField(required=False)
    telefone = forms.CharField(max_length=20, required=False)
    dominio = forms.CharField(max_length=253, required=False)
    observacoes_internas = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))
    pacote = forms.ModelChoiceField(queryset=Pacote.objects.filter(ativo=True))
    ciclo = forms.ChoiceField(choices=Ciclo.choices)
    limite_alunos_custom = forms.IntegerField(required=False, min_value=1)
    limite_professores_custom = forms.IntegerField(required=False, min_value=1)
    limite_unidades_custom = forms.IntegerField(required=False, min_value=1)
    motivo_excecao = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text="Obrigatorio quando houver limite customizado (fica registrado quem autorizou).",
    )

    def clean(self):
        dados = super().clean()
        customizados = [
            dados.get("limite_alunos_custom"),
            dados.get("limite_professores_custom"),
            dados.get("limite_unidades_custom"),
        ]
        if any(customizados) and not (dados.get("motivo_excecao") or "").strip():
            self.add_error("motivo_excecao", "Explique o motivo da excecao comercial.")
        return dados


class FaturaManualForm(EstiloMixin, forms.Form):
    descricao = forms.CharField(max_length=120, label="Descricao")
    valor = forms.DecimalField(max_digits=10, decimal_places=2, min_value=0)
    vencimento = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    desconto = forms.DecimalField(max_digits=10, decimal_places=2, min_value=0, initial=0)


class ConfiguracaoPlataformaForm(EstiloMixin, forms.ModelForm):
    class Meta:
        model = ConfiguracaoPlataforma
        fields = [
            "nome_emitente",
            "cnpj_emitente",
            "email_financeiro",
            "asaas_api_key",
            "asaas_ambiente",
            "asaas_base_url",
            "token_webhook",
            "trial_dias",
            "dias_bloqueio",
            "dias_suspensao",
            "multa_percentual",
            "juros_dia_percentual",
            "regua_ativa",
        ]
        widgets = {
            "asaas_api_key": forms.PasswordInput(render_value=True),
            "token_webhook": forms.PasswordInput(render_value=True),
        }


class ImpersonarForm(EstiloMixin, forms.Form):
    motivo = forms.CharField(
        label="Motivo do acesso (obrigatorio)",
        widget=forms.Textarea(attrs={"rows": 2}),
        max_length=500,
    )
    usuario_alvo = forms.CharField(required=False, label="Usuario alvo (opcional)", max_length=150)
