"""Formularios do CRM e da retencao."""

from __future__ import annotations

from django import forms

from relacionamento.models import InteracaoComLead, Lead, PerfilDeRisco


class LeadForm(forms.ModelForm):
    class Meta:
        model = Lead
        fields = [
            "nome",
            "telefone",
            "email",
            "origem",
            "interesse",
            "valor_estimado",
            "responsavel",
            "proximo_contato_em",
            "observacoes",
        ]
        widgets = {
            "proximo_contato_em": forms.DateInput(attrs={"type": "date"}),
            "observacoes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, rede=None, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            campo.widget.attrs.setdefault(
                "class", "mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            )
        if rede is not None:
            self.fields["responsavel"].queryset = (
                self.fields["responsavel"].queryset.filter(vinculos__rede=rede).distinct()
            )


class InteracaoForm(forms.ModelForm):
    class Meta:
        model = InteracaoComLead
        fields = ["tipo", "resumo", "resultado", "proximo_contato_em"]
        widgets = {
            "proximo_contato_em": forms.DateInput(attrs={"type": "date"}),
            "resumo": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            campo.widget.attrs.setdefault(
                "class", "mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            )


class DesfechoForm(forms.Form):
    desfecho = forms.ChoiceField(choices=PerfilDeRisco.Desfecho.choices, label="Desfecho")
    observacoes = forms.CharField(
        required=False, label="Observações", widget=forms.Textarea(attrs={"rows": 2})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            campo.widget.attrs.setdefault(
                "class", "mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            )


class PerderLeadForm(forms.Form):
    motivo = forms.CharField(label="Motivo da perda", max_length=200)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["motivo"].widget.attrs.setdefault(
            "class", "mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
        )
