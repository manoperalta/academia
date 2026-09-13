"""Formularios do site publico."""

from __future__ import annotations

from django import forms

from plataforma.models import Pacote
from plataforma.servicos import cnpj_em_uso, slug_disponivel
from plataforma.validadores import normalizar_cnpj, sugerir_slug, validar_cnpj


class EstiloPublicoMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            if isinstance(campo.widget, forms.CheckboxInput):
                campo.widget.attrs["class"] = (
                    "mt-1 h-4 w-4 rounded border-slate-300 text-emerald-600"
                )
            elif isinstance(campo.widget, forms.Textarea):
                campo.widget.attrs["class"] = (
                    "w-full rounded-lg border border-slate-300 px-3 py-2 text-sm shadow-sm "
                    "focus:border-emerald-500 focus:outline-none"
                )
            else:
                campo.widget.attrs["class"] = (
                    "w-full rounded-lg border border-slate-300 px-3 py-2 text-sm shadow-sm "
                    "focus:border-emerald-500 focus:outline-none"
                )


class CadastroPublicoForm(EstiloPublicoMixin, forms.Form):
    """Dados da academia + modalidade escolhida (RF-PLT-030)."""

    nome = forms.CharField(max_length=150, label="Nome da academia")
    cnpj = forms.CharField(
        max_length=20,
        required=False,
        label="CNPJ",
        help_text="Opcional, mas ajuda na emissao fiscal.",
    )
    responsavel = forms.CharField(max_length=150, label="Seu nome")
    email = forms.EmailField(label="E-mail do responsavel")
    telefone = forms.CharField(max_length=20, required=False, label="Telefone/WhatsApp")
    slug = forms.CharField(
        max_length=60,
        label="Endereco da sua academia",
        help_text="Letras, numeros e hifen. Ex.: academia-forca",
    )
    modalidade = forms.ChoiceField(
        choices=[("trial", "Testar 14 dias gratis"), ("pagamento", "Assinar agora com Pix")],
        initial="trial",
        label="Como quer comecar",
        widget=forms.RadioSelect,
    )
    aceite = forms.BooleanField(
        label="Concordo com o uso dos dados para a prestacao do servico.",
        error_messages={"required": "Precisamos do seu aceite para criar a conta."},
    )

    def __init__(self, *args, pacote: Pacote | None = None, **kwargs):
        from plataforma.servicos import compra_de_pacote_liberada

        super().__init__(*args, **kwargs)
        self.pacote = pacote
        self.compra_liberada = compra_de_pacote_liberada()
        if not self.compra_liberada:
            # Compra de pacote desabilitada na plataforma (interruptor do Django admin):
            # o cadastro segue existindo, mas sem vender pacote -- so o periodo de teste.
            self.fields["modalidade"].choices = [("trial", "Testar os dias de teste gratis")]
            self.fields["modalidade"].initial = "trial"
            self.fields["modalidade"].help_text = (
                "A compra de pacote esta desabilitada nesta plataforma. "
                "Fale com o comercial para assinar."
            )
        if not self.is_bound and pacote is not None and not self.initial.get("slug"):
            self.fields["slug"].initial = ""

    def clean_slug(self):
        slug = (self.cleaned_data["slug"] or "").strip().lower()
        if not slug:
            slug = sugerir_slug(self.cleaned_data.get("nome", ""))
        liberado, mensagem = slug_disponivel(slug)
        if not liberado:
            raise forms.ValidationError(mensagem)
        return slug

    def clean_cnpj(self):
        cnpj = self.cleaned_data.get("cnpj", "")
        if not cnpj:
            return ""
        if not validar_cnpj(cnpj):
            raise forms.ValidationError("CNPJ invalido. Confira os numeros.")
        if cnpj_em_uso(cnpj):
            raise forms.ValidationError(
                "Ja existe uma academia com este CNPJ. Fale com o suporte para recuperar o acesso."
            )
        return normalizar_cnpj(cnpj)

    def clean(self):
        dados = super().clean()
        if self.pacote is None:
            raise forms.ValidationError("Escolha um pacote para continuar.")
        if not self.pacote.ativo or not self.pacote.visivel_no_site:
            raise forms.ValidationError("Este pacote nao esta disponivel. Escolha outro.")
        return dados


class ContatoForm(EstiloPublicoMixin, forms.Form):
    nome = forms.CharField(max_length=150, label="Nome")
    email = forms.EmailField(label="E-mail")
    telefone = forms.CharField(max_length=20, required=False, label="Telefone")
    academia = forms.CharField(max_length=150, required=False, label="Academia")
    mensagem = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 4}), label="Como podemos ajudar?"
    )
