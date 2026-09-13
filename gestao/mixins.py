"""Mixins do painel: permissao por modulo, unidade atual e contexto comum."""

from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied

from core.mixins import EscritaPermitidaMixin, RedeRequiredMixin
from gestao.permissoes import pode, pode_editar


class PainelMixin(RedeRequiredMixin, EscritaPermitidaMixin, LoginRequiredMixin):
    """Base de toda tela do painel: vinculo com a rede, status e modulo.

    A ordem importa: valida o vinculo da rede (``RedeRequiredMixin``), bloqueia escrita
    quando a conta esta suspensa/somente leitura (``EscritaPermitidaMixin``) e por fim
    exige autenticacao (``LoginRequiredMixin``).
    """

    papeis_permitidos: list[str] = []
    modulo: str = ""
    nivel_minimo: str = "ver"
    titulo: str = "Painel"
    subtitulo: str = ""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if self.modulo and not pode(
            request.user,
            self.modulo,
            self.nivel_minimo,
            rede=getattr(request, "rede", None),
            unidade=getattr(request, "unidade", None),
        ):
            raise PermissionDenied("Seu papel nao permite acessar este modulo do painel.")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto.update(
            painel=True,
            modulo=self.modulo,
            titulo=self.titulo,
            subtitulo=self.subtitulo,
            unidade_atual=getattr(self.request, "unidade", None),
            pode_editar=pode_editar(
                self.request.user,
                self.modulo,
                rede=getattr(self.request, "rede", None),
                unidade=getattr(self.request, "unidade", None),
            )
            if self.modulo
            else False,
        )
        return contexto


class EdicaoMixin(PainelMixin):
    """Modulo em que a tela exige nivel de edicao."""

    nivel_minimo = "editar"
