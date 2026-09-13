"""Autenticacao por token de servico (``Authorization: Token <prefixo>.<segredo>``)."""

from __future__ import annotations

from rest_framework import authentication, exceptions

from api.models import ApiToken
from core.context import definir_contexto


class UsuarioServico:
    """Identidade usada quando a chamada vem de um token (nao e um usuario real)."""

    is_authenticated = True
    is_anonymous = False
    is_staff = False
    is_superuser = False

    def __init__(self, token: ApiToken):
        self.token = token
        self.pk = None
        self.id = None
        self.username = f"servico:{token.prefixo}"
        self.email = ""
        self.escopos = set(token.escopos or [])

    def __str__(self) -> str:
        return self.username

    def tem_escopo(self, escopo: str) -> bool:
        from api.escopos import tem_escopo

        return tem_escopo(self.escopos, escopo)


class TokenServicoAuthentication(authentication.BaseAuthentication):
    """Reconhece tokens de servico e cria o contexto de rede/unidade da chamada."""

    palavra_chave = "Token"

    def authenticate(self, request):
        cabecalho = authentication.get_authorization_header(request).split()
        if not cabecalho:
            return None
        if cabecalho[0].lower() != self.palavra_chave.lower().encode():
            return None
        if len(cabecalho) == 1:
            raise exceptions.AuthenticationFailed("Cabecalho de token sem credencial.")
        if len(cabecalho) > 2:
            raise exceptions.AuthenticationFailed("Credencial de token com espacos.")

        credencial = cabecalho[1].decode()
        token = ApiToken.por_credencial(credencial)
        if token is None:
            raise exceptions.AuthenticationFailed("Token invalido.")
        if not token.esta_valido():
            raise exceptions.AuthenticationFailed("Token inativo, revogado ou expirado.")

        ip = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip() or request.META.get(
            "REMOTE_ADDR"
        )
        token.marcar_uso(ip)
        definir_contexto(rede=token.rede, unidade=token.unidade, usuario=None)
        request.rede = token.rede
        request.unidade = token.unidade
        request.token_servico = token
        return (UsuarioServico(token), token)

    def authenticate_header(self, request):
        return self.palavra_chave
