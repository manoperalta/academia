"""Validacoes do cadastro publico (CNPJ numerico e alfanumerico, slug)."""

from __future__ import annotations

import re
import unicodedata

SLUGS_RESERVADOS = {
    "www",
    "api",
    "admin",
    "app",
    "apps",
    "gestao",
    "plataforma",
    "painel",
    "academia",
    "static",
    "media",
    "docs",
    "help",
    "suporte",
    "mail",
    "blog",
    "site",
    "sistema",
    "conta",
    "contas",
    "login",
    "cadastro",
    "planos",
    "sobre",
    "contato",
    "status",
}

PESOS_CNPJ = ([5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2], [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])


def normalizar_cnpj(cnpj: str) -> str:
    """Remove pontos, barras e espacos; mantem digitos e letras (CNPJ alfanumerico de 2026)."""
    return re.sub(r"[^0-9A-Za-z]", "", (cnpj or "")).upper()


def _valor(caractere: str) -> int:
    """Digitos valem o proprio numero; letras valem o codigo ASCII menos 48."""
    return int(caractere) if caractere.isdigit() else ord(caractere) - 48


def validar_cnpj(cnpj: str) -> bool:
    """Valida CNPJ pelos digitos verificadores (aceita numerico e alfanumerico)."""
    limpo = normalizar_cnpj(cnpj)
    if len(limpo) != 14:
        return False
    if limpo == limpo[0] * 14:
        return False
    for indice, pesos in enumerate(PESOS_CNPJ):
        soma = sum(_valor(c) * peso for c, peso in zip(limpo[: 12 + indice], pesos, strict=True))
        resto = soma % 11
        digito = "0" if resto < 2 else str(11 - resto)
        if limpo[12 + indice] != digito:
            return False
    return True


def sugerir_slug(nome: str, maximo: int = 60) -> str:
    """Transforma o nome da academia num slug utilizavel na URL."""
    base = unicodedata.normalize("NFKD", (nome or "").lower())
    base = "".join(c for c in base if not unicodedata.combining(c))
    base = re.sub(r"[^a-z0-9]+", "-", base).strip("-")
    return base[:maximo].strip("-") or "academia"


def validar_slug(slug: str) -> tuple[bool, str]:
    """Regras do identificador publico do tenant (path e subdominio)."""
    limpo = (slug or "").strip().lower()
    if len(limpo) < 3:
        return False, "O identificador precisa ter pelo menos 3 caracteres."
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", limpo):
        return False, "Use apenas letras, numeros e hifen (sem comecar ou terminar com hifen)."
    if limpo in SLUGS_RESERVADOS:
        return False, "Esse identificador e reservado pelo sistema. Escolha outro."
    return True, ""
