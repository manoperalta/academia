"""Telas de gamificacao: regras, conquistas e ranking."""

from __future__ import annotations

from django.views.generic import TemplateView

from gamificacao.forms import ConquistaForm, RegraDePontosForm
from gamificacao.models import Conquista, RegraDePontos
from gestao.mixins import PainelMixin
from gestao.painel_base import FormularioDoPainel
from gestao.permissoes import Modulo
from gestao.views import ListaPainel


class RegrasDePontosView(ListaPainel):
    model = RegraDePontos
    modulo = Modulo.GAMIFICACAO
    titulo = "Regras de pontos"
    subtitulo = "Quanto cada evento vale e o limite diario"
    colunas = (
        ("Evento", "get_evento_display"),
        ("Pontos", "pontos"),
        ("Limite por dia", "limite_diario"),
        ("Ativa", "ativo"),
    )
    ordenacao = ("evento",)
    url_novo = "gamificacao:regra_nova"
    url_editar = "gamificacao:regra_editar"


class RegraDePontosNovaView(FormularioDoPainel):
    form_class = RegraDePontosForm
    modulo = Modulo.GAMIFICACAO
    titulo = "Nova regra de pontos"
    sucesso_url = "gamificacao:regras"


class RegraDePontosEditarView(FormularioDoPainel):
    form_class = RegraDePontosForm
    modulo = Modulo.GAMIFICACAO
    titulo = "Editar regra de pontos"
    sucesso_url = "gamificacao:regras"

    def get_objeto(self):
        return RegraDePontos.objects.filter(pk=self.kwargs["pk"]).first()


class ConquistasView(ListaPainel):
    model = Conquista
    modulo = Modulo.GAMIFICACAO
    titulo = "Conquistas"
    subtitulo = "Selos liberados por quantidade de eventos"
    colunas = (
        ("Nome", "nome"),
        ("Evento", "get_evento_display"),
        ("Necessario", "quantidade"),
        ("Bonus", "pontos_bonus"),
        ("Ativa", "ativa"),
    )
    ordenacao = ("evento", "quantidade")
    url_novo = "gamificacao:conquista_nova"
    url_editar = "gamificacao:conquista_editar"


class ConquistaNovaView(FormularioDoPainel):
    form_class = ConquistaForm
    modulo = Modulo.GAMIFICACAO
    titulo = "Nova conquista"
    sucesso_url = "gamificacao:conquistas"


class ConquistaEditarView(FormularioDoPainel):
    form_class = ConquistaForm
    modulo = Modulo.GAMIFICACAO
    titulo = "Editar conquista"
    sucesso_url = "gamificacao:conquistas"

    def get_objeto(self):
        return Conquista.objects.filter(pk=self.kwargs["pk"]).first()


class RankingView(PainelMixin, TemplateView):
    modulo = Modulo.GAMIFICACAO
    titulo = "Ranking e engajamento"
    template_name = "gamificacao/ranking.html"
    nivel_minimo = "ver"

    def get_context_data(self, **kwargs):
        from gamificacao.servicos import engajamento_do_mes, ranking

        contexto = super().get_context_data(**kwargs)
        unidade = getattr(self.request, "unidade", None)
        contexto["ranking"] = ranking(rede=self.request.rede, unidade=unidade, limite=20)
        contexto["engajamento"] = engajamento_do_mes(self.request.rede)
        return contexto
