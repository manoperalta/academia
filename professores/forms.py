"""Formularios do cadastro de professor.

Esta e a casca **Bootstrap** (a mesma do cadastro de aluno, em ``usuarios/forms.py``): a tela
do dashboard usa este formulario, e as regras de negocio ficam em ``professores.servicos``
e em ``gestao.forms.criar_ou_vincular_usuario`` -- as duas telas (dashboard e painel de
gestao) gravam pelo mesmo caminho.
"""

from __future__ import annotations

from django import forms
from django.contrib.auth import get_user_model

from . import servicos
from .models import Professor

CAMPOS = [
    "nome",
    "data_nasc",
    "cpf_cnpj_prof",
    "email_prof",
    "telefone_prof",
    "endereco_prof",
    "numero_end_prof",
    "bairro_prof",
    "cep_prof",
    "status_prof",
    "foto_prof",
]

WIDGETS = {
    "data_nasc": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    "nome": forms.TextInput(attrs={"class": "form-control"}),
    "cpf_cnpj_prof": forms.TextInput(attrs={"class": "form-control"}),
    "email_prof": forms.EmailInput(attrs={"class": "form-control", "placeholder": "email@exemplo.com"}),
    "telefone_prof": forms.TextInput(
        attrs={"class": "form-control", "placeholder": "(00) 00000-0000"}
    ),
    "endereco_prof": forms.TextInput(attrs={"class": "form-control"}),
    "numero_end_prof": forms.TextInput(attrs={"class": "form-control"}),
    "bairro_prof": forms.TextInput(attrs={"class": "form-control"}),
    "cep_prof": forms.TextInput(attrs={"class": "form-control"}),
    "status_prof": forms.Select(attrs={"class": "form-select"}),
    "foto_prof": forms.ClearableFileInput(attrs={"class": "form-control"}),
}


class ProfessorForm(forms.ModelForm):
    """Cadastro/edicao de professor com acesso, unidades de atendimento e valor da hora."""

    criar_login = forms.BooleanField(
        required=False,
        initial=True,
        label="Criar acesso ao sistema",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )
    senha = forms.CharField(
        required=False,
        label="Senha inicial",
        widget=forms.PasswordInput(attrs={"class": "form-control"}, render_value=False),
        help_text="Em branco = o sistema gera uma senha temporaria.",
    )
    valor_por_hora = forms.DecimalField(
        label="Valor por hora (R$)",
        required=False,
        min_value=0,
        max_digits=12,
        decimal_places=2,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
        help_text="Quanto este professor recebe por hora. Aparece no financeiro dele.",
    )
    unidades = forms.ModelMultipleChoiceField(
        label="Unidades de atendimento",
        required=False,
        queryset=servicos.unidades_da_rede(None),
        widget=forms.CheckboxSelectMultiple(attrs={"class": "form-check-input"}),
        help_text="O professor abre a agenda por unidade; escolha todas em que ele atende.",
    )

    class Meta:
        model = Professor
        fields = CAMPOS
        widgets = WIDGETS

    def __init__(self, *args, rede=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.rede = rede
        self.senha_temporaria = ""
        self.fields["unidades"].queryset = servicos.unidades_da_rede(rede)
        if self.instance and self.instance.pk:
            self.fields["unidades"].initial = list(
                servicos.unidades_do_professor(self.instance).values_list("pk", flat=True)
            )
            if self.instance.user_id:
                self.fields["criar_login"].initial = True
                self.fields["criar_login"].help_text = "O acesso deste cadastro ja existe."
            if self.instance.valor_por_hora is not None:
                self.fields["valor_por_hora"].initial = self.instance.valor_por_hora
        elif rede is not None:
            unidades = list(self.fields["unidades"].queryset)
            if len(unidades) == 1:
                self.fields["unidades"].initial = [unidades[0].pk]

    def clean(self):
        dados = super().clean()
        unidades = dados.get("unidades") or []
        if not unidades and self.fields["unidades"].queryset.exists():
            self.add_error(
                "unidades", "Escolha ao menos uma unidade de atendimento para este professor."
            )
        email = (dados.get("email_prof") or "").strip().lower()
        if dados.get("criar_login") and email and not (self.instance and self.instance.user_id):
            modelo = get_user_model()
            existente = (
                modelo.objects.filter(username__iexact=email).first()
                or modelo.objects.filter(email__iexact=email).first()
            )
            if existente is not None and getattr(existente, "professor_profile", None) is not None:
                self.add_error(
                    "email_prof",
                    "Este e-mail ja tem cadastro de professor. Edite o cadastro existente.",
                )
        return dados

    def save(self, commit=True):
        professor = super().save(commit=commit)
        if not commit:
            return professor
        self.salvar_acesso(professor)
        servicos.sincronizar_unidades(professor, list(self.cleaned_data.get("unidades") or []))
        servicos.aplicar_valor_por_hora(professor, self.cleaned_data.get("valor_por_hora"))
        return professor

    def salvar_acesso(self, professor) -> None:
        """Cria/reaproveita o login do professor (mesma rotina do painel de gestao)."""
        from gestao.forms import criar_ou_vincular_usuario

        self.senha_temporaria = ""
        if not self.cleaned_data.get("criar_login") or professor.user_id:
            return
        usuario, temporaria = criar_ou_vincular_usuario(
            self.cleaned_data.get("email_prof"),
            self.cleaned_data.get("senha"),
            {"is_professor": True},
        )
        if usuario is None:
            return
        professor.user = usuario
        professor.save(update_fields=["user"])
        self.senha_temporaria = temporaria


class ProfessorProfileForm(forms.ModelForm):
    """Perfil que o proprio professor completa (sem acesso, sem unidades)."""

    class Meta:
        model = Professor
        fields = [
            "nome",
            "data_nasc",
            "cpf_cnpj_prof",
            "email_prof",
            "telefone_prof",
            "endereco_prof",
            "numero_end_prof",
            "bairro_prof",
            "cep_prof",
            "foto_prof",
        ]
        widgets = {nome: widget for nome, widget in WIDGETS.items() if nome != "status_prof"}
