"""E-mails da plataforma (boas-vindas, cobranca e avisos institucionais).

Usa as configuracoes de e-mail do proprio projeto (env EMAIL_*), porque o tenant
recem-criado ainda nao tem SMTP proprio configurado.
"""
from __future__ import annotations

import logging

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger("plataforma")


def enviar_email_plataforma(assunto: str, corpo: str, destinatarios) -> bool:
    """Envia e-mail em nome da plataforma. Devolve True quando o backend aceitou."""
    if isinstance(destinatarios, str):
        destinos = [destinatarios] if destinatarios else []
    else:
        destinos = [destino for destino in list(destinatarios or []) if destino]
    if not destinos:
        logger.info("e-mail da plataforma ignorado (sem destinatario): %s", assunto)
        return False
    remetente = getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@safestack.com.br")
    try:
        send_mail(assunto, corpo, remetente, destinos, fail_silently=False)
    except Exception as erro:  # noqa: BLE001 - falha de e-mail nao derruba o cadastro
        logger.warning("falha ao enviar e-mail da plataforma (%s): %s", assunto, erro)
        return False
    return True
