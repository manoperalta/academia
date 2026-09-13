"""Formularios de remuneracao."""

from __future__ import annotations

from django import forms

from remuneracao.models import RegraDeComissao


class RegraDeComissaoForm(forms.ModelForm):
    class Meta:
        model = RegraDeComissao
        fields = [
            "professor",
            "unidade",
            "tipo",
            "valor",
            "percentual",
            "piso_mensal",
            "teto_mensal",
            "inicio_vigencia",
            "fim_vigencia",
            "ativo",
            "descricao",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            campo.widget.attrs.setdefault(
                "class", "w-full rounded-lg border border-slate-300 px-3 py-2"
            )
