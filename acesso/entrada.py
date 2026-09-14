"""Tela de entrada depois do login: por onde o usuario continua.

Quem opera a plataforma (dono/equipe) escolhe entre o painel da plataforma -- que enxerga
todas as academias --, o painel de gestao da rede ativa e o dashboard da academia. Os
demais usuarios caem direto no ambiente da rede em que tem vinculo, que era o
comportamento antigo (``LOGIN_REDIRECT_URL = "dashboard"`` para todo mundo).
"""

from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import TemplateView

from gestao.permissoes import modulos_visiveis


def operador_da_plataforma(usuario) -> bool:
    """Dono/equipe da SafeStack: enxerga todas as academias da base."""
    return bool(getattr(usuario, "is_superuser", False) or getattr(usuario, "is_staff", False))


class EscolherPainelView(LoginRequiredMixin, TemplateView):
    """Porta de entrada: so o dono escolhe; os demais vao para a academia do vinculo."""

    template_name = "acesso/escolher_painel.html"

    def get(self, request, *args, **kwargs):
        if not operador_da_plataforma(request.user):
            return redirect("dashboard")
        return super().get(request, *args, **kwargs)

    def destinos(self) -> list[dict]:
        usuario = self.request.user
        rede = getattr(self.request, "rede", None)
        unidade = getattr(self.request, "unidade", None)
        opcoes = [
            {
                "rotulo": "Painel da plataforma",
                "descricao": (
                    "Todas as academias da base: planos, cobrancas, faturas, suporte e "
                    "impersonacao de uma rede."
                ),
                "rota": reverse("plataforma:metricas"),
                "icone": "fas fa-globe",
            }
        ]
        if modulos_visiveis(usuario, rede=rede, unidade=unidade):
            sufixo = f" — {rede.nome}" if rede is not None else ""
            opcoes.append(
                {
                    "rotulo": f"Painel de gestao{sufixo}",
                    "descricao": (
                        "Operacao da academia: alunos, professores, aulas, agenda e financeiro "
                        "da rede ativa."
                    ),
                    "rota": reverse("gestao:visao_geral"),
                    "icone": "fas fa-sliders-h",
                }
            )
        opcoes.append(
            {
                "rotulo": "Dashboard da academia",
                "descricao": "Visao rapida do dia: indicadores, pagamentos e avisos.",
                "rota": reverse("dashboard"),
                "icone": "fas fa-chart-line",
            }
        )
        return opcoes

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["destinos"] = self.destinos()
        return contexto
