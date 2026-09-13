"""Mixins do painel da plataforma e bloqueio por modulo do pacote."""
from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied

from plataforma.servicos import e_equipe_plataforma, impersonacao_ativa, modulo_disponivel


class PlataformaMixin(LoginRequiredMixin):
    """Area restrita a equipe da SafeStack."""

    titulo = "Plataforma"
    subtitulo = ""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not e_equipe_plataforma(request.user):
            raise PermissionDenied("Area restrita a equipe SafeStack.")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto.update(
            plataforma=True,
            titulo=self.titulo,
            subtitulo=self.subtitulo,
            impersonacao=impersonacao_ativa(self.request),
        )
        return contexto


class ModuloDePacoteMixin:
    """Bloqueia no servidor o que nao esta no pacote do tenant (RF-PLT-011)."""

    modulo_pacote = ""

    def dispatch(self, request, *args, **kwargs):
        if self.modulo_pacote and not modulo_disponivel(
            getattr(request, "rede", None), self.modulo_pacote
        ):
            raise PermissionDenied(
                f"O recurso '{self.get_modulo_pacote_display()}' nao esta incluido no seu pacote. "
                "Fale com a SafeStack para fazer upgrade."
            )
        return super().dispatch(request, *args, **kwargs)

    def get_modulo_pacote_display(self) -> str:
        from plataforma.models import ModuloPacote

        return dict(ModuloPacote.choices).get(self.modulo_pacote, self.modulo_pacote)
