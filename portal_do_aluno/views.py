"""Telas do portal do aluno, sempre no escopo do proprio aluno logado."""

from __future__ import annotations

from django.contrib import messages
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import TemplateView

from agendamento.models import Agendamento
from painel.models import Painel
from portal_do_aluno import servicos
from portal_do_aluno.models import PreferenciaDeNotificacao
from portal_do_aluno.servicos import ErroDoPortal


class PortalDoAlunoMixin:
    """Resolve o aluno da sessao; sem perfil de aluno, 404 (nao vaza a existencia da area)."""

    def aluno(self, request):
        from area_do_aluno.views import aluno_da_sessao

        aluno = aluno_da_sessao(request)
        if aluno is None:
            raise Http404("sem-perfil-de-aluno")
        return aluno

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["aluno"] = self.aluno(self.request)
        return contexto


class AgendaDoAlunoView(PortalDoAlunoMixin, TemplateView):
    template_name = "portal/agenda.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        aluno = contexto["aluno"]
        contexto["turmas"] = servicos.turmas_disponiveis(aluno)
        contexto["meus"] = servicos.meus_agendamentos(aluno)
        return contexto


class BuscarHorariosView(PortalDoAlunoMixin, TemplateView):
    """Busca de horarios por unidade, professor e tipo de atividade (com os filtros da rede)."""

    template_name = "portal/buscar_horarios.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        aluno = contexto["aluno"]
        filtros = servicos.filtros_da_busca(aluno)
        unidade_id = self.request.GET.get("unidade") or ""
        professor_id = self.request.GET.get("professor") or ""
        atividade = self.request.GET.get("atividade") or ""
        unidade = next((u for u in filtros["unidades"] if str(u.pk) == unidade_id), None)
        professor = next((p for p in filtros["professores"] if str(p.pk) == professor_id), None)
        contexto.update(filtros)
        contexto["filtro"] = {
            "unidade": unidade_id,
            "professor": professor_id,
            "atividade": atividade,
        }
        contexto["horarios"] = servicos.buscar_horarios(
            aluno, unidade=unidade, professor=professor, atividade=atividade
        )
        return contexto


class AgendarView(PortalDoAlunoMixin, View):
    def post(self, request, pk: int, *args, **kwargs):
        aluno = self.aluno(request)
        # manager global: o portal do aluno roda fora do contexto de tenant do painel
        turma = Painel.todos.filter(pk=pk, rede=aluno.rede, arquivado_em__isnull=True).first()
        if turma is None:
            messages.error(request, "Turma nao encontrada.")
            return redirect("portal:agenda")
        try:
            servicos.agendar(aluno=aluno, turma=turma)
        except ErroDoPortal as erro:
            messages.error(request, str(erro))
        else:
            messages.success(request, f"Voce esta agendado em {turma.nome} ({turma.data:%d/%m}).")
        return redirect("portal:agenda")


class ListaDeEsperaView(PortalDoAlunoMixin, View):
    def post(self, request, pk: int, *args, **kwargs):
        aluno = self.aluno(request)
        turma = get_object_or_404(
            Painel.todos.filter(rede=aluno.rede, arquivado_em__isnull=True), pk=pk
        )
        try:
            servicos.entrar_na_lista_de_espera(aluno=aluno, turma=turma)
        except ErroDoPortal as erro:
            messages.error(request, str(erro))
        else:
            messages.success(request, "Voce entrou na lista de espera; avisamos quando abrir vaga.")
        return redirect("portal:agenda")


class CancelarAgendamentoView(PortalDoAlunoMixin, View):
    def post(self, request, pk: int, *args, **kwargs):
        aluno = self.aluno(request)
        agendamento = get_object_or_404(
            Agendamento.todos.filter(aluno=aluno.user, rede=aluno.rede), pk=pk
        )
        try:
            resultado = servicos.cancelar_agendamento(aluno=aluno, agendamento=agendamento)
        except ErroDoPortal as erro:
            messages.error(request, str(erro))
        else:
            aviso = (
                f" O próximo da fila ({resultado['avisado']}) foi avisado."
                if resultado["avisado"]
                else ""
            )
            messages.success(request, "Agendamento cancelado." + aviso)
        return redirect("portal:agenda")


class MeusPagamentosView(PortalDoAlunoMixin, TemplateView):
    template_name = "portal/pagamentos.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["faturas"] = servicos.minhas_faturas(contexto["aluno"])
        return contexto


class MinhaFichaView(PortalDoAlunoMixin, TemplateView):
    template_name = "portal/ficha.html"

    def get_context_data(self, **kwargs):
        from usuarios.models import FichaSaude

        contexto = super().get_context_data(**kwargs)
        contexto["ficha"] = FichaSaude.todos.filter(usuario=contexto["aluno"]).first()
        return contexto

    def post(self, request, *args, **kwargs):

        aluno = self.aluno(request)
        try:
            servicos.salvar_ficha(
                aluno=aluno,
                altura=request.POST.get("altura") or 0,
                peso=request.POST.get("peso") or 0,
                restricoes=request.POST.get("restricoes", ""),
                prescricoes=request.POST.get("prescricoes", ""),
                usa_medicamento=request.POST.get("usa_medicamento") == "on",
                qual_medicamento=request.POST.get("qual_medicamento", ""),
                observacoes=request.POST.get("observacoes", ""),
            )
        except Exception as erro:  # pragma: no cover - validacao do banco
            messages.error(request, f"Nao consegui salvar a ficha: {erro}")
        else:
            messages.success(request, "Ficha de saude atualizada.")
        return redirect("portal:ficha")


class PerfilDoAlunoView(PortalDoAlunoMixin, TemplateView):
    template_name = "portal/perfil.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["preferencias"] = servicos.preferencias_do_aluno(contexto["aluno"])
        contexto["canais"] = PreferenciaDeNotificacao.Canal.choices
        return contexto

    def post(self, request, *args, **kwargs):
        aluno = self.aluno(request)
        try:
            servicos.salvar_preferencias(
                aluno=aluno,
                canal=request.POST.get("canal", "whatsapp"),
                avisar_vencimento=request.POST.get("avisar_vencimento") == "on",
                avisar_aula=request.POST.get("avisar_aula") == "on",
                avisar_aniversario=request.POST.get("avisar_aniversario") == "on",
                receber_novidades=request.POST.get("receber_novidades") == "on",
            )
        except ErroDoPortal as erro:
            messages.error(request, str(erro))
        else:
            messages.success(request, "Preferencias salvas.")
        return redirect("portal:perfil")


class MeusDadosView(PortalDoAlunoMixin, View):
    """LGPD: o aluno baixa tudo o que a academia guarda sobre ele."""

    def get(self, request, *args, **kwargs):
        aluno = self.aluno(request)
        conteudo = servicos.meus_dados_em_json(aluno)
        resposta = HttpResponse(conteudo, content_type="application/json")
        resposta["Content-Disposition"] = 'attachment; filename="meus-dados.json"'
        return resposta
