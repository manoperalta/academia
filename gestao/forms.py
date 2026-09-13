"""Formularios do painel, ligados aos modelos reais do sistema."""

from __future__ import annotations

from datetime import timedelta

from django import forms
from django.contrib.auth import get_user_model
from django.db import models as dj_models
from django.utils.crypto import get_random_string

from academia.models import Configuracao, IdentidadeVisual
from aulas.models import Aulas
from core.models import ConviteEquipe
from core.papeis import Papel
from financeiro.models import Despesa, Pagamento, Plano
from notificacoes.models import ConfiguracaoEmail, ConfiguracaoWhatsapp
from painel.models import Painel
from professores.models import Professor
from usuarios.models import FichaSaude, Usuario

CAMPO = (
    "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 "
    "shadow-sm focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
)
MARCADOR = "h-4 w-4 rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"


class EstiloMixin:
    """Aplica o estilo do painel a todos os widgets do formulario."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            if isinstance(campo.widget, (forms.CheckboxInput,)):
                campo.widget.attrs["class"] = MARCADOR
            elif isinstance(campo.widget, (forms.CheckboxSelectMultiple, forms.RadioSelect)):
                campo.widget.attrs["class"] = "space-y-1 text-sm"
            else:
                campo.widget.attrs["class"] = CAMPO


def gerar_senha() -> str:
    return get_random_string(10)


def criar_ou_vincular_usuario(email, senha, flags: dict) -> tuple[object | None, str]:
    """Reaproveita (ou cria) o usuario de login e devolve (usuario, senha_temporaria)."""
    if not email:
        return None, ""
    modelo = get_user_model()
    email = email.strip().lower()
    usuario = (
        modelo.objects.filter(username__iexact=email).first()
        or modelo.objects.filter(email__iexact=email).first()
    )
    if usuario is not None:
        atualizados = []
        for campo, valor in flags.items():
            if valor and not getattr(usuario, campo, False):
                setattr(usuario, campo, valor)
                atualizados.append(campo)
        if atualizados:
            usuario.save(update_fields=atualizados)
        return usuario, ""
    temporaria = senha or gerar_senha()
    usuario = modelo(username=email, email=email)
    usuario.set_password(temporaria)
    for campo, valor in flags.items():
        setattr(usuario, campo, valor)
    usuario.save()
    return usuario, ("" if senha else temporaria)


class PessoaForm(EstiloMixin, forms.ModelForm):
    """Base para aluno e professor: cria o acesso (login) junto com o cadastro."""

    criar_login = forms.BooleanField(required=False, initial=True, label="Criar acesso ao sistema")
    senha = forms.CharField(
        required=False,
        label="Senha inicial",
        widget=forms.PasswordInput(render_value=False),
        help_text="Em branco = o sistema gera uma senha temporaria.",
    )

    campo_email = "email_user"
    flag_usuario: dict = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.senha_temporaria = ""
        if self.instance and self.instance.pk and self.instance.user_id:
            self.fields["criar_login"].initial = True
            self.fields["criar_login"].help_text = "O acesso deste cadastro ja existe."
        for nome in ("criar_login", "senha"):
            campo = self.fields[nome]
            campo.widget.attrs["class"] = MARCADOR if nome == "criar_login" else CAMPO

    def save(self, commit=True):
        instancia = super().save(commit=False)
        criar = self.cleaned_data.get("criar_login")
        if criar and not (instancia.pk and instancia.user_id):
            usuario, temporaria = criar_ou_vincular_usuario(
                self.cleaned_data.get(self.campo_email),
                self.cleaned_data.get("senha"),
                self.flag_usuario,
            )
            if usuario is not None:
                instancia.user = usuario
                self.senha_temporaria = temporaria
        if commit:
            instancia.save()
        return instancia


class AlunoForm(PessoaForm):
    class Meta:
        model = Usuario
        fields = [
            "nome",
            "data_nasc",
            "cpf_cnpj_user",
            "email_user",
            "telefone_user",
            "endereco_user",
            "numero_end_user",
            "bairro_user",
            "cep_user",
            "status_user",
            "foto_user",
        ]
        widgets = {"data_nasc": forms.DateInput(attrs={"type": "date"})}

    campo_email = "email_user"
    flag_usuario = {"is_student": True}


class ProfessorForm(PessoaForm):
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
            "status_prof",
            "foto_prof",
        ]
        widgets = {"data_nasc": forms.DateInput(attrs={"type": "date"})}

    campo_email = "email_prof"
    flag_usuario = {"is_professor": True}


class FichaSaudeForm(EstiloMixin, forms.ModelForm):
    class Meta:
        model = FichaSaude
        fields = [
            "altura",
            "peso",
            "restricoes",
            "prescricoes",
            "obs",
            "usa_medicamento",
            "qual_medicamento",
        ]


class AulaForm(EstiloMixin, forms.ModelForm):
    class Meta:
        model = Aulas
        fields = [
            "nome",
            "descricao",
            "professor",
            "categorias_exercicios",
            "restricao",
            "file_de_video",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        modelo = get_user_model()
        ids = Professor.objects.exclude(user__isnull=True).values_list("user_id", flat=True)
        self.fields["professor"].queryset = modelo.objects.filter(
            dj_models.Q(pk__in=list(ids)) | dj_models.Q(is_superuser=True)
        ).distinct()
        self.fields["professor"].label_from_instance = lambda u: (
            u.get_full_name() or u.get_username()
        )
        self.fields["file_de_video"].required = False


class PainelForm(EstiloMixin, forms.ModelForm):
    class Meta:
        model = Painel
        fields = ["nome", "data", "hora_inicio", "hora_fim", "responsavel", "numero_de_user"]
        widgets = {
            "data": forms.DateInput(attrs={"type": "date"}),
            "hora_inicio": forms.TimeInput(attrs={"type": "time"}),
            "hora_fim": forms.TimeInput(attrs={"type": "time"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["responsavel"].queryset = (
            self.fields["responsavel"].queryset.filter(is_active=True).order_by("first_name")
        )
        self.fields["responsavel"].label_from_instance = lambda u: (
            u.get_full_name() or u.get_username()
        )


class PlanoForm(EstiloMixin, forms.ModelForm):
    class Meta:
        model = Plano
        fields = ["nome", "tipo", "valor", "descricao", "imagem"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["imagem"].required = False


class PagamentoForm(EstiloMixin, forms.ModelForm):
    DIAS_POR_TIPO = {"semanal": 7, "mensal": 30, "semestral": 180, "anual": 365}

    class Meta:
        model = Pagamento
        fields = ["usuario", "plano", "valor_pago", "data_inicio", "data_fim", "status"]
        widgets = {
            "data_inicio": forms.DateInput(attrs={"type": "date"}),
            "data_fim": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["data_fim"].required = False
        self.fields["data_fim"].help_text = "Em branco = calculado pela periodicidade do plano."
        self.fields["usuario"].queryset = self.fields["usuario"].queryset.filter(is_student=True)
        self.fields["usuario"].label_from_instance = lambda u: u.get_full_name() or u.get_username()

    def save(self, commit=True):
        pagamento = super().save(commit=False)
        if not pagamento.data_fim and pagamento.data_inicio:
            if pagamento.plano is not None:
                dias = self.DIAS_POR_TIPO.get(pagamento.plano.tipo, 30)
                pagamento.data_fim = pagamento.data_inicio + timedelta(days=dias)
            else:
                pagamento.data_fim = pagamento.data_inicio
        if commit:
            pagamento.save()
        return pagamento


class DespesaForm(EstiloMixin, forms.ModelForm):
    class Meta:
        model = Despesa
        fields = ["descricao", "valor", "data", "categoria"]
        widgets = {"data": forms.DateInput(attrs={"type": "date"})}


class ConfiguracaoForm(EstiloMixin, forms.ModelForm):
    class Meta:
        model = Configuracao
        fields = [
            "titulo",
            "cnpj",
            "ie",
            "endereco",
            "numero",
            "cep",
            "theme_mode",
            "dias_alerta_vencimento",
            "mensagem_pagamento_atrasado",
            "mensagem_aniversario",
        ]


class IdentidadeForm(EstiloMixin, forms.ModelForm):
    class Meta:
        model = IdentidadeVisual
        fields = ["logotipo", "favicon"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for nome in ("logotipo", "favicon"):
            self.fields[nome].required = False


class EmailConfigForm(EstiloMixin, forms.ModelForm):
    class Meta:
        model = ConfiguracaoEmail
        fields = [
            "host",
            "port",
            "username",
            "password",
            "use_tls",
            "use_ssl",
            "remetente_nome",
            "remetente_email",
            "ativo",
        ]
        widgets = {"password": forms.PasswordInput(render_value=True)}


class WhatsappConfigForm(EstiloMixin, forms.ModelForm):
    class Meta:
        model = ConfiguracaoWhatsapp
        fields = ["access_token", "phone_number_id", "business_account_id", "ativo"]
        widgets = {"access_token": forms.PasswordInput(render_value=True)}


class ConviteForm(EstiloMixin, forms.ModelForm):
    """Convite para a equipe -- aceita mais de um papel (rede + unidade)."""

    papeis = forms.MultipleChoiceField(
        label="Papéis",
        widget=forms.CheckboxSelectMultiple,
        help_text=(
            "Marque um ou mais papéis. O administrador da rede e o gestor da "
            "unidade podem ser a mesma pessoa."
        ),
    )

    class Meta:
        model = ConviteEquipe
        fields = ["email", "papeis", "unidade"]
        labels = {"email": "E-mail", "papeis": "Papéis", "unidade": "Unidade"}

    def __init__(self, *args, usuario=None, unidades=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["papeis"].choices = [(p.value, p.label) for p in Papel if p != Papel.ALUNO]
        if self.instance and self.instance.pk:
            self.initial["papeis"] = self.instance.lista_de_papeis()
        if unidades is not None:
            self.fields["unidade"].queryset = unidades
        self.fields["unidade"].required = False
        self.fields["unidade"].help_text = (
            "Em branco = acesso a todas as unidades da rede. Papéis de rede "
            "(admin, financeiro, auditor) valem para a rede inteira."
        )

    def clean_papeis(self):
        papeis = self.cleaned_data["papeis"]
        if not papeis:
            raise forms.ValidationError("Marque pelo menos um papel.")
        return papeis

    def save(self, commit=True):
        convite = super().save(commit=False)
        papeis = list(self.cleaned_data["papeis"])
        convite.papeis = papeis
        convite.papel = papeis[0]
        if commit:
            convite.save()
        return convite


class NovaContaForm(EstiloMixin, forms.Form):
    """Usado no aceite do convite por quem ainda nao tem login."""

    nome = forms.CharField(max_length=150, label="Seu nome")
    senha = forms.CharField(label="Crie uma senha", widget=forms.PasswordInput, min_length=8)
    senha2 = forms.CharField(label="Repita a senha", widget=forms.PasswordInput)

    def clean(self):
        dados = super().clean()
        if dados.get("senha") and dados.get("senha") != dados.get("senha2"):
            self.add_error("senha2", "As senhas nao conferem.")
        return dados
