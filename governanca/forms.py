"""Formularios de autenticacao e 2FA."""
from __future__ import annotations

from django import forms


class EstiloSeguroMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            campo.widget.attrs["class"] = (
                "w-full rounded-lg border border-slate-300 px-3 py-2 text-sm shadow-sm "
                "focus:border-emerald-500 focus:outline-none"
            )


class LoginSeguroForm(EstiloSeguroMixin, forms.Form):
    identificador = forms.CharField(label="E-mail", max_length=200)
    senha = forms.CharField(label="Senha", widget=forms.PasswordInput)


class Codigo2FAForm(EstiloSeguroMixin, forms.Form):
    codigo = forms.CharField(
        label="Codigo do app (ou um codigo de recuperacao)", max_length=20,
        widget=forms.TextInput(attrs={"autocomplete": "one-time-code", "autofocus": "autofocus"}),
    )

    def clean_codigo(self):
        codigo = (self.cleaned_data["codigo"] or "").strip()
        if not codigo:
            raise forms.ValidationError("Informe o codigo de 6 digitos.")
        return codigo


class Desativar2FAForm(EstiloSeguroMixin, forms.Form):
    senha = forms.CharField(label="Sua senha", widget=forms.PasswordInput)
    codigo = forms.CharField(label="Codigo atual do app", max_length=20)
