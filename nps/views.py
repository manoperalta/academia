"""Telas de NPS: pesquisas, painel de resultado e fila de detratores."""

from __future__ import annotations

from django.contrib import messages
from django.shortcuts import redirect
from django.views import View
from django.views.generic import TemplateView

from gestao.mixins import PainelMixin
from gestao.painel_base import FormularioDoPainel
from gestao.permissoes import Modulo
from gestao.views import ListaPainel
from nps.forms import PesquisaForm
from nps.models import Pesquisa
from nps.servicos import detratores_para_tratar, marcar_tratada, nps, resumo_por_unidade


class PesquisasView(ListaPainel):
    model = Pesquisa
    modulo = Modulo.PESQUISAS
    titulo = "Pesquisas"
    subtitulo = "NPS pos-aula, pos-atendimento ou trimestral"
    colunas = (
        ("Titulo", "titulo"),
        ("Tipo", "get_tipo_display"),
        ("Unidade", "unidade"),
        ("Ativa", "ativa"),
        ("Inicio", "inicio"),
    )
    ordenacao = ("-criado_em",)
    url_novo = "nps:pesquisa_nova"
    url_editar = "nps:pesquisa_editar"


class PesquisaNovaView(FormularioDoPainel):
    form_class = PesquisaForm
    modulo = Modulo.PESQUISAS
    titulo = "Nova pesquisa"
    sucesso_url = "nps:pesquisas"


class PesquisaEditarView(FormularioDoPainel):
    form_class = PesquisaForm
    modulo = Modulo.PESQUISAS
    titulo = "Editar pesquisa"
    sucesso_url = "nps:pesquisas"

    def get_objeto(self):
        return Pesquisa.objects.filter(pk=self.kwargs["pk"]).first()


class PainelDoNpsView(PainelMixin, TemplateView):
    modulo = Modulo.PESQUISAS
    titulo = "NPS da rede"
    template_name = "nps/painel.html"
    nivel_minimo = "ver"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        rede = self.request.rede
        unidade = getattr(self.request, "unidade", None)
        contexto["resultado"] = nps(unidade=unidade)
        contexto["por_unidade"] = resumo_por_unidade(rede)
        contexto["detratores"] = detratores_para_tratar(rede=rede, unidade=unidade)
        return contexto


class TratarDetratorView(PainelMixin, View):
    modulo = Modulo.PESQUISAS
    nivel_minimo = "editar"

    def post(self, request, *args, **kwargs):
        from nps.models import Resposta

        resposta = Resposta.objects.filter(pk=self.kwargs["pk"]).first()
        if resposta is None:
            messages.error(request, "Resposta nao encontrada.")
        else:
            marcar_tratada(resposta, request.user, request.POST.get("observacao", ""))
            messages.success(request, "Tratativa registrada.")
        return redirect("nps:painel")
