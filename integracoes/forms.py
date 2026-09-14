"""Formulario da tela de integracoes: os campos vem do provedor selecionado."""

from __future__ import annotations

from django import forms
from django.core.exceptions import ValidationError

from gestao.forms import CAMPO, MARCADOR
from integracoes import catalogo
from integracoes.catalogo import ARQUIVO, BOOLEANO, INTEIRO, SELECAO, SENHA, URL

#: Aviso padrao de campo de segredo ja gravado.
MANTER = "Ja existe um valor gravado: deixe em branco para manter o atual."


def campo_do_catalogo(campo: catalogo.Campo, valor_atual: str = ""):
    """Transforma a declaracao do catalogo em campo de formulario."""
    ja_tem_valor = bool(valor_atual)
    obrigatorio = campo.obrigatorio and not ja_tem_valor
    ajuda = campo.ajuda
    if campo.exemplo:
        ajuda = f"{ajuda} Ex.: {campo.exemplo}".strip()
    if campo.sensivel and ja_tem_valor:
        ajuda = f"{ajuda} {MANTER}".strip()
    comum = {"label": campo.rotulo, "help_text": ajuda, "required": obrigatorio}

    if campo.tipo == SENHA:
        return forms.CharField(
            widget=forms.PasswordInput(render_value=False, attrs={"class": CAMPO, "autocomplete": "new-password"}),
            **comum,
        )
    if campo.tipo == URL:
        return forms.URLField(widget=forms.URLInput(attrs={"class": CAMPO}), **comum)
    if campo.tipo == INTEIRO:
        return forms.IntegerField(
            min_value=1,
            max_value=65535 if campo.nome in {"porta", "port"} else None,
            widget=forms.NumberInput(attrs={"class": CAMPO}),
            **comum,
        )
    if campo.tipo == BOOLEANO:
        return forms.BooleanField(
            widget=forms.CheckboxInput(attrs={"class": MARCADOR}),
            required=False,
            **{k: v for k, v in comum.items() if k != "required"},
        )
    if campo.tipo == SELECAO:
        escolhas = list(campo.opcoes)
        if not obrigatorio:
            escolhas = [("", "---------"), *escolhas]
        return forms.ChoiceField(
            choices=escolhas, widget=forms.Select(attrs={"class": CAMPO}), **comum
        )
    if campo.tipo == ARQUIVO:
        return forms.FileField(
            widget=forms.ClearableFileInput(attrs={"class": CAMPO}), **comum
        )
    return forms.CharField(widget=forms.TextInput(attrs={"class": CAMPO}), **comum)


def formulario_do_provedor(chave: str, *, valores: dict | None = None, **kwargs):
    """Monta (na hora) o formulario com os campos daquele provedor.

    ``valores`` traz o que ja esta gravado. Campo de segredo entra vazio de proposito: o
    valor atual nunca e devolvido para a tela, so mantido quando o campo fica em branco.
    """
    integracao = catalogo.obter(chave)
    if integracao is None:
        raise ValidationError(f"Provedor desconhecido: {chave}")
    valores = valores or {}
    campos = {}
    iniciais = {}
    for campo in integracao.campos:
        gravado = valores.get(campo.nome, "")
        campos[campo.nome] = campo_do_catalogo(campo, gravado)
        if gravado and not campo.sensivel:
            iniciais[campo.nome] = gravado  # o operador ve o que esta configurado
    #: Campo de segredo nao recebe valor inicial: nunca volta para a tela.

    classe = type("FormularioDeIntegracao", (forms.Form,), campos)
    formulario = classe(initial=iniciais, **kwargs)
    formulario.provedor = chave
    return formulario


class EscolherProvedorForm(forms.Form):
    """Selecao do provedor. Ao enviar, a tela recarrega com os campos daquele provedor."""

    provedor = forms.ChoiceField(
        label="Integracao",
        choices=[(chave, integracao.nome) for chave, integracao in catalogo.CATALOGO.items()],
        widget=forms.Select(attrs={"class": CAMPO}),
    )
