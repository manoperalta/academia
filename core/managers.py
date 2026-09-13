"""
Managers e querysets escopados por rede.

Regra de ouro do isolamento:

* ``Model.objects``  -> respeita a rede do contexto atual. Sem contexto, devolve
  tudo (compatibilidade com a instalacao de rede unica). Este e o manager que o
  codigo novo deve usar para trabalhar DENTRO de uma rede.
* ``Model.todos``    -> nunca filtra. Uso restrito a codigo de plataforma
  (metricas globais, provisionamento, migracoes) e sempre auditado.

A defesa em profundidade esta descrita no PRD (secao 5.3): manager escopado +
middleware + base do modelo + testes de isolamento obrigatorios.
"""

from __future__ import annotations

from django.db import models

from core.context import rede_atual, unidade_atual


class TenantQuerySet(models.QuerySet):
    """QuerySet com atalhos de escopo e operacoes de arquivamento."""

    def da_rede(self, rede):
        return self.filter(rede=rede)

    def da_unidade(self, unidade):
        return self.filter(unidade=unidade)

    def ativos(self):
        return self.filter(arquivado_em__isnull=True)

    def arquivados(self):
        return self.filter(arquivado_em__isnull=False)

    def arquivar(self):
        from django.utils import timezone

        return self.update(arquivado_em=timezone.now())

    def restaurar(self):
        return self.update(arquivado_em=None)


class TenantManager(models.Manager.from_queryset(TenantQuerySet)):
    """Manager que aplica o escopo da rede (e, se pedido, da unidade) do contexto."""

    use_in_migrations = False

    def get_queryset(self):
        qs = super().get_queryset()
        rede = rede_atual()
        if rede is not None and rede.pk is not None:
            qs = qs.filter(rede_id=rede.pk)
        return qs

    def escopo_unidade(self):
        """Escopo explicito por unidade do contexto (usado quando o recorte importa)."""
        qs = self.get_queryset()
        unidade = unidade_atual()
        if unidade is not None and unidade.pk is not None:
            qs = qs.filter(models.Q(unidade_id=unidade.pk) | models.Q(unidade__isnull=True))
        return qs


class SemEscopoManager(models.Manager.from_queryset(TenantQuerySet)):
    """Manager sem escopo algum. Use com consciencia: atravessa redes."""

    def get_queryset(self):
        return super().get_queryset()


class AtivoManager(TenantManager):
    """Somente registros nao arquivados."""

    def get_queryset(self):
        return super().get_queryset().filter(arquivado_em__isnull=True)
