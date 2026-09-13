"""Formularios da rede: unidades, metas, repasses, governanca, comunicados e onboarding."""

from __future__ import annotations

from datetime import timedelta

from django import forms
from django.utils import timezone

from core.models import Unidade
from rede.models import (
    Comunicado,
    Meta,
    PoliticaDaRede,
    RegraDeRepasse,
    TemplateDeUnidade,
)


class EstiloDaRedeMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            if isinstance(campo.widget, (forms.CheckboxInput,)):
                campo.widget.attrs["class"] = "h-4 w-4 rounded border-slate-300"
            else:
                campo.widget.attrs["class"] = (
                    "w-full rounded-lg border border-slate-300 px-3 py-2 text-sm "
                    "focus:border-emerald-500 focus:outline-none"
                )


class UnidadeForm(EstiloDaRedeMixin, forms.ModelForm):
    class Meta:
        model = Unidade
        fields = [
            "nome",
            "codigo",
            "tipo",
            "cnpj",
            "endereco",
            "cidade",
            "uf",
            "telefone",
            "gestor",
            "status",
            "sobrescrever_branding",
        ]
        widgets = {"sobrescrever_branding": forms.CheckboxInput()}

    def __init__(self, *args, rede=None, **kwargs):
        super().__init__(*args, **kwargs)
        if rede is not None:
            from django.contrib.auth import get_user_model

            self.fields["gestor"].queryset = (
                get_user_model()
                .objects.filter(vinculos__rede=rede, vinculos__ativo=True)
                .distinct()
            )


class MetaForm(EstiloDaRedeMixin, forms.ModelForm):
    class Meta:
        model = Meta
        fields = ["unidade", "indicador", "inicio", "fim", "alvo"]
        widgets = {
            "inicio": forms.DateInput(attrs={"type": "date"}),
            "fim": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, rede=None, **kwargs):
        super().__init__(*args, **kwargs)
        if rede is not None:
            self.fields["unidade"].queryset = Unidade.objects.filter(rede=rede)
        hoje = timezone.localdate()
        self.fields["inicio"].initial = self.fields["inicio"].initial or hoje.replace(day=1)
        self.fields["fim"].initial = self.fields["fim"].initial or (
            hoje.replace(day=1) + timedelta(days=32)
        ).replace(day=1) - timedelta(days=1)


class RegraDeRepasseForm(EstiloDaRedeMixin, forms.ModelForm):
    class Meta:
        model = RegraDeRepasse
        fields = [
            "unidade",
            "tipo",
            "percentual",
            "valor_fixo",
            "base",
            "excluir_taxas_de_gateway",
            "percentual_de_taxas_de_gateway",
            "excluir_estornos",
            "excluir_impostos",
            "percentual_de_impostos",
            "excluir_planos_de_parceiros",
            "fundo_de_marketing",
            "piso_minimo",
            "dia_de_vencimento",
            "inicio_da_vigencia",
            "fim_da_vigencia",
            "ativo",
        ]
        widgets = {
            "inicio_da_vigencia": forms.DateInput(attrs={"type": "date"}),
            "fim_da_vigencia": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, rede=None, **kwargs):
        super().__init__(*args, **kwargs)
        if rede is not None:
            self.fields["unidade"].queryset = Unidade.objects.filter(rede=rede)
        self.fields["unidade"].empty_label = "Padrao da rede (todas as unidades)"

    def clean(self):
        dados = super().clean()
        if dados.get("tipo") == RegraDeRepasse.Tipo.PERCENTUAL and not dados.get("percentual"):
            self.add_error("percentual", "Informe o percentual do royalty.")
        if dados.get("tipo") in {
            RegraDeRepasse.Tipo.FIXO,
            RegraDeRepasse.Tipo.PERCENTUAL_MAIS_FIXO,
        } and not dados.get("valor_fixo"):
            self.add_error("valor_fixo", "Informe o valor fixo do periodo.")
        return dados


class PoliticaDaRedeForm(EstiloDaRedeMixin, forms.ModelForm):
    class Meta:
        model = PoliticaDaRede
        exclude = ["rede", "atualizado_em"]


class ComunicadoForm(EstiloDaRedeMixin, forms.ModelForm):
    class Meta:
        model = Comunicado
        fields = ["unidade", "titulo", "mensagem", "publico", "exige_confirmacao", "ativo"]
        widgets = {"mensagem": forms.Textarea(attrs={"rows": 5})}

    def __init__(self, *args, rede=None, **kwargs):
        super().__init__(*args, **kwargs)
        if rede is not None:
            self.fields["unidade"].queryset = Unidade.objects.filter(rede=rede)
        self.fields["unidade"].empty_label = "Todas as unidades"


class TemplateDeUnidadeForm(EstiloDaRedeMixin, forms.ModelForm):
    class Meta:
        model = TemplateDeUnidade
        fields = ["nome", "descricao", "configuracoes", "ativo"]
        widgets = {
            "configuracoes": forms.Textarea(
                attrs={
                    "rows": 6,
                    "placeholder": '{"planos": ["Mensal"], "grades": ["manha"], "mensagens": ["boas-vindas"], '
                    '"usuarios_padrao": ["recepcao"], "branding": {"sobrescrever": false}}',
                }
            )
        }

    def clean_configuracoes(self):
        dados = self.cleaned_data["configuracoes"]
        if isinstance(dados, dict):
            return dados
        import json

        try:
            return json.loads(dados or "{}")
        except json.JSONDecodeError as erro:
            raise forms.ValidationError(f"JSON invalido: {erro}") from erro


class DistribuicaoForm(EstiloDaRedeMixin, forms.Form):
    referencia = forms.CharField(label="Aula/treino da rede (codigo ou nome)", max_length=120)
    unidades = forms.ModelMultipleChoiceField(
        label="Distribuir para",
        queryset=Unidade.objects.none(),
        widget=forms.CheckboxSelectMultiple(attrs={"class": "h-4 w-4"}),
    )

    def __init__(self, *args, rede=None, **kwargs):
        super().__init__(*args, **kwargs)
        if rede is not None:
            self.fields["unidades"].queryset = Unidade.objects.filter(rede=rede, status="ativa")


class TransferenciaForm(EstiloDaRedeMixin, forms.Form):
    origem = forms.ModelChoiceField(label="Unidade de origem", queryset=Unidade.objects.none())
    destino = forms.ModelChoiceField(label="Unidade de destino", queryset=Unidade.objects.none())
    motivo = forms.CharField(label="Motivo", max_length=200, required=False)

    def __init__(self, *args, rede=None, **kwargs):
        super().__init__(*args, **kwargs)
        if rede is not None:
            self.fields["origem"].queryset = Unidade.objects.filter(rede=rede)
            self.fields["destino"].queryset = Unidade.objects.filter(rede=rede)

    def clean(self):
        dados = super().clean()
        if dados.get("origem") and dados.get("origem") == dados.get("destino"):
            self.add_error("destino", "Escolha uma unidade de destino diferente da origem.")
        return dados


class AprovacaoDecisaoForm(EstiloDaRedeMixin, forms.Form):
    justificativa = forms.CharField(
        label="Justificativa", widget=forms.Textarea(attrs={"rows": 3}), required=False
    )


class ImportacaoDaRedeForm(EstiloDaRedeMixin, forms.Form):
    tipo = forms.ChoiceField(
        label="O que importar", choices=[("alunos", "Alunos"), ("professores", "Professores")]
    )
    arquivo = forms.FileField(label="Planilha CSV (com a coluna 'unidade')")
    atualizar_existentes = forms.BooleanField(label="Atualizar quem ja existe", required=False)
