"""TOTP (RFC 6238) -- vetores oficiais da RFC."""
from __future__ import annotations

import base64

from core import totp

SEGREDO_RFC = base64.b32encode(b"12345678901234567890").decode().rstrip("=")


def test_vetores_da_rfc_6238():
    """Vetores da RFC (SHA-1) nos instantes 59, 1111111109, 1111111111 e 1234567890."""
    assert totp.codigo_atual(SEGREDO_RFC, instante=59, digitos=8) == "94287082"
    assert totp.codigo_atual(SEGREDO_RFC, instante=1111111109, digitos=8) == "07081804"
    assert totp.codigo_atual(SEGREDO_RFC, instante=1111111111, digitos=8) == "14050471"
    assert totp.codigo_atual(SEGREDO_RFC, instante=1234567890, digitos=8) == "89005924"


def test_codigo_de_seis_digitos():
    codigo = totp.codigo_atual(SEGREDO_RFC, instante=59)
    assert len(codigo) == 6 and codigo.isdigit()


def test_validar_aceita_janela_e_recusa_codigo_errado():
    codigo = totp.codigo_atual(SEGREDO_RFC, instante=1000)
    assert totp.validar(SEGREDO_RFC, codigo, instante=1000) is True
    assert totp.validar(SEGREDO_RFC, codigo, instante=1030) is True   # uma janela adiante
    assert totp.validar(SEGREDO_RFC, codigo, instante=1200) is False  # longe demais
    assert totp.validar(SEGREDO_RFC, "000000", instante=1000) is False
    assert totp.validar(SEGREDO_RFC, "abc", instante=1000) is False


def test_gerar_segredo_e_uri():
    segredo = totp.gerar_segredo()
    assert len(segredo) >= 16 and segredo.isupper()
    uri = totp.uri_otpauth(segredo, "dono@academia.com.br")
    assert uri.startswith("otpauth://totp/") and segredo in uri and "issuer=" in uri
