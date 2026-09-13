"""JWT HS256 proprio (sem dependencia externa) para a API v1 (PRD 20.2)."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

from django.conf import settings

ALGORITMO = "HS256"
EMISSOR = "academia-api"
VALIDADE_DO_ACESSO = 3600
VALIDADE_DA_RENOVACAO = 60 * 60 * 24 * 14


class TokenInvalido(Exception):
    """Token ausente, expirado, com assinatura errada ou emissor desconhecido."""


def _segredo() -> bytes:
    return (getattr(settings, "API_JWT_SECRET", "") or settings.SECRET_KEY).encode("utf-8")


def _b64(dados: bytes) -> str:
    return base64.urlsafe_b64encode(dados).rstrip(b"=").decode("ascii")


def _de_b64(texto: str) -> bytes:
    return base64.urlsafe_b64decode(texto + "=" * (-len(texto) % 4))


def _assinar(cabecalho: str, corpo: str) -> str:
    mensagem = f"{cabecalho}.{corpo}".encode("ascii")
    return _b64(hmac.new(_segredo(), mensagem, hashlib.sha256).digest())


def emitir(subject: str, escopos=None, tipo: str = "acesso", validade: int | None = None,
           extra: dict | None = None) -> str:
    agora = int(time.time())
    validade = validade if validade is not None else (
        VALIDADE_DO_ACESSO if tipo == "acesso" else VALIDADE_DA_RENOVACAO
    )
    cabecalho = _b64(json.dumps({"alg": ALGORITMO, "typ": "JWT"}, separators=(",", ":")).encode())
    corpo = _b64(json.dumps(
        {"sub": str(subject), "iss": EMISSOR, "iat": agora, "exp": agora + validade,
         "tipo": tipo, "escopos": list(escopos or []), **(extra or {})},
        separators=(",", ":"), sort_keys=True,
    ).encode())
    return f"{cabecalho}.{corpo}.{_assinar(cabecalho, corpo)}"


def validar(token: str, tipo: str | None = None) -> dict:
    if not token or token.count(".") != 2:
        raise TokenInvalido("Token malformado.")
    cabecalho, corpo, assinatura = token.split(".")
    if not hmac.compare_digest(assinatura, _assinar(cabecalho, corpo)):
        raise TokenInvalido("Assinatura invalida.")
    try:
        dados = json.loads(_de_b64(corpo))
        cabecalho_dados = json.loads(_de_b64(cabecalho))
    except (ValueError, json.JSONDecodeError) as erro:
        raise TokenInvalido("Conteudo ilegivel.") from erro
    if cabecalho_dados.get("alg") != ALGORITMO:
        raise TokenInvalido("Algoritmo nao aceito.")
    if dados.get("iss") != EMISSOR:
        raise TokenInvalido("Emissor desconhecido.")
    if int(dados.get("exp", 0)) < int(time.time()):
        raise TokenInvalido("Token expirado.")
    if tipo and dados.get("tipo") != tipo:
        raise TokenInvalido(f"Token de {dados.get('tipo')} nao serve aqui.")
    return dados
