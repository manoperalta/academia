"""Envio de e-mail usando o SMTP que a propria academia configurou."""

from __future__ import annotations

from django.conf import settings
from django.core.mail import EmailMessage, get_connection

from notificacoes.models import ConfiguracaoEmail


def configuracao_ativa(rede):
    """Configuracao de e-mail ativa da rede (ou None)."""
    if rede is None:
        return None
    return ConfiguracaoEmail.todos.filter(rede=rede, ativo=True).first()


def conexao_e_remetente(rede):
    """Devolve (conexao, remetente). Conexao None = usar o backend padrao."""
    config = configuracao_ativa(rede)
    if config is None:
        return None, getattr(settings, "DEFAULT_FROM_EMAIL", "nao-responda@localhost")
    conexao = get_connection(
        host=config.host,
        port=config.port,
        username=config.username,
        password=config.password,
        use_tls=config.use_tls,
        use_ssl=config.use_ssl,
        fail_silently=False,
    )
    remetente = config.remetente_email or getattr(
        settings, "DEFAULT_FROM_EMAIL", "no-reply@localhost"
    )
    return conexao, remetente


def enviar_email(rede, assunto: str, corpo: str, destinatarios: list[str]) -> str:
    """Envia o e-mail e devolve o remetente usado. Levanta excecao se o SMTP falhar."""
    conexao, remetente = conexao_e_remetente(rede)
    mensagem = EmailMessage(assunto, corpo, remetente, destinatarios, connection=conexao)
    mensagem.send(fail_silently=False)
    return remetente
