"""
Contexto de requisicao (rede/unidade/usuario) via thread-local.

Por que thread-local e nao "passar por parametro": o codigo atual (views, forms,
templates, signals) foi escrito para uma instalacao de rede unica. O contexto
permite escopar as consultas sem reescrever todas as chamadas de uma vez -- e o
mesmo mecanismo que o middleware usa para descobrir em qual rede a requisicao
esta acontecendo.

Regra: tudo que e escrito em codigo novo deve receber o contexto explicitamente
(services) e apenas o codigo legado depende do contexto implicito.
"""

from __future__ import annotations

import threading

from django.core.exceptions import ImproperlyConfigured

_estado = threading.local()


def definir_contexto(*, rede=None, unidade=None, usuario=None) -> None:
    """Define o contexto da requisicao atual (usado pelo middleware)."""
    _estado.rede = rede
    _estado.unidade = unidade
    _estado.usuario = usuario


def limpar_contexto() -> None:
    """Limpa o contexto ao fim da requisicao (evita vazamento entre threads)."""
    for atributo in ("rede", "unidade", "usuario"):
        if hasattr(_estado, atributo):
            delattr(_estado, atributo)


def rede_atual():
    """Rede da requisicao atual, ou ``None``."""
    return getattr(_estado, "rede", None)


def unidade_atual():
    """Unidade da requisicao atual, ou ``None``."""
    return getattr(_estado, "unidade", None)


def usuario_atual():
    """Usuario da requisicao atual, ou ``None``."""
    return getattr(_estado, "usuario", None)


def exigir_rede():
    """Devolve a rede atual ou levanta erro (para codigo que nao aceita None)."""
    rede = rede_atual()
    if rede is None:
        raise ImproperlyConfigured(
            "Nenhuma rede no contexto: use core.tenancy.usar_rede(), "
            "o middleware RedeMiddleware, ou passe rede= explicitamente."
        )
    return rede


class UsarRede:
    """Context manager: ``with usar_rede(rede): ...`` (scripts, testes, tasks)."""

    def __init__(self, rede, unidade=None, usuario=None):
        self._novo = (rede, unidade, usuario)
        self._anterior = (rede_atual(), unidade_atual(), usuario_atual())

    def __enter__(self):
        definir_contexto(rede=self._novo[0], unidade=self._novo[1], usuario=self._novo[2])
        return self._novo[0]

    def __exit__(self, *exc):
        definir_contexto(
            rede=self._anterior[0], unidade=self._anterior[1], usuario=self._anterior[2]
        )
        return False


def usar_rede(rede, unidade=None, usuario=None) -> UsarRede:
    """Atalho legivel para ``UsarRede`` (padrao CapWords fica na classe)."""
    return UsarRede(rede, unidade=unidade, usuario=usuario)
