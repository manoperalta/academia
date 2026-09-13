"""TOTP (RFC 6238) sem dependencia externa.

Usado no 2FA do painel (RNF-009). Compatível com Google Authenticator, Authy,
1Password e afins (SHA-1, 6 digitos, janela de 30s).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote

DIGITOS_PADRAO = 6
JANELA_PADRAO = 30
ALFABETO_BASE32 = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"


def gerar_segredo(tamanho: int = 20) -> str:
    """Segredo base32 (sem padding), no formato que os apps esperam."""
    return base64.b32encode(secrets.token_bytes(tamanho)).decode("ascii").rstrip("=")


def _contador(instante: float | None, janela: int) -> int:
    return int((time.time() if instante is None else instante) // janela)


def _codigo_do_contador(segredo: str, contador: int, digitos: int) -> str:
    preenchido = segredo.upper() + "=" * (-len(segredo) % 8)
    chave = base64.b32decode(preenchido, casefold=True)
    resumo = hmac.new(chave, struct.pack(">Q", contador), hashlib.sha1).digest()
    deslocamento = resumo[-1] & 0x0F
    numero = struct.unpack(">I", resumo[deslocamento : deslocamento + 4])[0] & 0x7FFFFFFF
    return str(numero % (10**digitos)).zfill(digitos)


def codigo_atual(segredo: str, instante: float | None = None, digitos: int = DIGITOS_PADRAO,
                 janela: int = JANELA_PADRAO) -> str:
    return _codigo_do_contador(segredo, _contador(instante, janela), digitos)


def validar(segredo: str, codigo: str, instante: float | None = None, digitos: int = DIGITOS_PADRAO,
            janela: int = JANELA_PADRAO, tolerancia: int = 1) -> bool:
    """Aceita o codigo atual e os vizinhos (+-tolerancia janelas) para tolerar relogio atrasado."""
    codigo = (codigo or "").strip().replace(" ", "")
    if not codigo.isdigit() or len(codigo) != digitos:
        return False
    base = _contador(instante, janela)
    return any(
        hmac.compare_digest(_codigo_do_contador(segredo, base + deslocamento, digitos), codigo)
        for deslocamento in range(-tolerancia, tolerancia + 1)
    )


def uri_otpauth(segredo: str, conta: str, emissor: str = "Academia SaaS",
                digitos: int = DIGITOS_PADRAO, janela: int = JANELA_PADRAO) -> str:
    """URI para o app autenticador (mostrada como QR ou digitada a mao)."""
    rotulo = quote(f"{emissor}:{conta}")
    parametros = f"secret={segredo}&issuer={quote(emissor)}&algorithm=SHA1&digits={digitos}&period={janela}"
    return f"otpauth://totp/{rotulo}?{parametros}"
