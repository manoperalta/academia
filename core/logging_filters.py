"""Filtros de log que carimbam a rede da requisicao (RNF-008)."""

from __future__ import annotations

from core.context import rede_atual


class FiltroRede:
    """Adiciona ``rede_id`` nas linhas de log para separar clientes."""

    def filter(self, record):
        rede = rede_atual()
        record.rede_id = getattr(rede, "pk", None) or "-"
        return True
