"""Telas do funil de captacao e da fila de retencao."""

from __future__ import annotations

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import DetailView, ListView, TemplateView

from gestao.mixins import EdicaoMixin, PainelMixin
from gestao.permissoes import Modulo
from relacionamento import servicos
from relacionamento.forms import DesfechoForm, InteracaoForm, LeadForm, PerderLeadForm
from relacionamento.models import Lead, OrigemDoLead, PerfilDeRisco
from relacionamento.servicos import ErroDeRelacionamento


def _leads_do_painel(request):
    return Lead.objects.filter(rede=request.rede).select_related("unidade", "responsavel", "aluno")


class FunilView(PainelMixin, TemplateView):
    """Onde o funil vaza: conversao por origem e tempo ate matricula."""

    modulo = Modulo.CRM
    template_name = "relacionamento/funil.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["funil"] = servicos.funil(self.request.rede)
        contexto["retencao"] = servicos.resumo_da_retencao(self.request.rede)
        contexto["para_contato"] = servicos.leads_para_contato(self.request.rede, limite=10)
        return contexto


class ListaDeLeadsView(PainelMixin, ListView):
    modulo = Modulo.CRM
    template_name = "relacionamento/leads.html"
    context_object_name = "leads"
    paginate_by = 25

    def get_queryset(self):
        consulta = _leads_do_painel(self.request)
        situacao = self.request.GET.get("situacao", "").strip()
        origem = self.request.GET.get("origem", "").strip()
        if situacao:
            consulta = consulta.filter(situacao=situacao)
        if origem:
            consulta = consulta.filter(origem=origem)
        return consulta

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["form"] = LeadForm(rede=self.request.rede)
        contexto["situacoes"] = Lead.Situacao.choices
        contexto["origens"] = OrigemDoLead.choices
        contexto["filtro_situacao"] = self.request.GET.get("situacao", "")
        contexto["filtro_origem"] = self.request.GET.get("origem", "")
        return contexto

    def post(self, request, *args, **kwargs):
        form = LeadForm(request.POST, rede=request.rede)
        if form.is_valid():
            lead = form.save(commit=False)
            lead.rede = request.rede
            lead.unidade = getattr(request.user, "unidade", None)
            lead.save()
            messages.success(request, f"Lead {lead.nome} registrado.")
            return redirect("relacionamento:lead", pk=lead.pk)
        self.object_list = self.get_queryset()
        contexto = self.get_context_data()
        contexto["form"] = form
        return self.render_to_response(contexto)


class LeadDetalheView(PainelMixin, DetailView):
    modulo = Modulo.CRM
    template_name = "relacionamento/lead_detalhe.html"
    context_object_name = "lead"

    def get_queryset(self):
        return _leads_do_painel(self.request)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["interacoes"] = self.object.interacoes.select_related("feito_por")
        contexto["form"] = InteracaoForm()
        contexto["form_perda"] = PerderLeadForm()
        return contexto


class RegistrarInteracaoView(EdicaoMixin, View):
    modulo = Modulo.CRM

    def post(self, request, pk: int, *args, **kwargs):
        lead = get_object_or_404(_leads_do_painel(request), pk=pk)
        form = InteracaoForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Preencha o tipo e o resumo do contato.")
            return redirect("relacionamento:lead", pk=lead.pk)
        dados = form.cleaned_data
        try:
            servicos.registrar_interacao(
                lead=lead,
                tipo=dados["tipo"],
                resumo=dados["resumo"],
                feito_por=request.user,
                resultado=dados.get("resultado", ""),
                proximo_contato_em=dados.get("proximo_contato_em"),
            )
        except ErroDeRelacionamento as erro:
            messages.error(request, str(erro))
        else:
            messages.success(request, "Contato registrado e funil atualizado.")
        return redirect("relacionamento:lead", pk=lead.pk)


class ConverterLeadView(EdicaoMixin, View):
    """Cria a matricula a partir do lead, com login sem senha utilizavel."""

    modulo = Modulo.CRM

    def post(self, request, pk: int, *args, **kwargs):
        lead = get_object_or_404(_leads_do_painel(request), pk=pk)
        try:
            lead, perfil = servicos.matricular_lead(lead=lead, criado_por=request.user)
        except ErroDeRelacionamento as erro:
            messages.error(request, str(erro))
        else:
            messages.success(
                request, f"Matricula criada para {perfil.nome}. Defina a senha no primeiro acesso."
            )
        return redirect("relacionamento:lead", pk=lead.pk)


class PerderLeadView(EdicaoMixin, View):
    modulo = Modulo.CRM

    def post(self, request, pk: int, *args, **kwargs):
        lead = get_object_or_404(_leads_do_painel(request), pk=pk)
        form = PerderLeadForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Informe o motivo da perda.")
        else:
            try:
                servicos.marcar_perdido(lead=lead, motivo=form.cleaned_data["motivo"])
            except ErroDeRelacionamento as erro:
                messages.error(request, str(erro))
            else:
                messages.success(request, "Lead marcado como perdido.")
        return redirect("relacionamento:lead", pk=lead.pk)


class FilaDeRetencaoView(PainelMixin, ListView):
    """Quem esta em risco, com a conta aberta e a acao sugerida."""

    modulo = Modulo.RETENCAO
    template_name = "relacionamento/retencao.html"
    context_object_name = "perfis"
    paginate_by = 25

    def get_queryset(self):
        consulta = PerfilDeRisco.objects.filter(rede=self.request.rede).select_related(
            "aluno", "unidade", "responsavel"
        )
        faixa = self.request.GET.get("faixa", "").strip()
        if faixa:
            consulta = consulta.filter(faixa=faixa)
        return consulta

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["resumo"] = servicos.resumo_da_retencao(self.request.rede)
        contexto["faixas"] = PerfilDeRisco.Faixa.choices
        contexto["filtro_faixa"] = self.request.GET.get("faixa", "")
        contexto["form"] = DesfechoForm()
        return contexto


class AtualizarRiscoView(EdicaoMixin, View):
    """Recalcula o risco da rede; com ``?dry_run=1`` apenas mostra o que mudaria."""

    modulo = Modulo.RETENCAO

    def post(self, request, *args, **kwargs):
        simulacao = request.POST.get("dry_run") in {"1", "true", "on"}
        resultado = servicos.atualizar_perfis_de_risco(request.rede, dry_run=simulacao)
        from django.shortcuts import render

        return render(
            request,
            "relacionamento/risco_resultado.html",
            {
                "resultado": resultado,
                "rede": request.rede,
            },
        )


class DesfechoView(EdicaoMixin, View):
    modulo = Modulo.RETENCAO

    def post(self, request, pk: int, *args, **kwargs):
        perfil = get_object_or_404(PerfilDeRisco.objects.filter(rede=request.rede), pk=pk)
        form = DesfechoForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Desfecho invalido.")
            return redirect("relacionamento:retencao")
        try:
            servicos.registrar_desfecho(
                perfil=perfil,
                desfecho=form.cleaned_data["desfecho"],
                observacoes=form.cleaned_data.get("observacoes", ""),
                responsavel=request.user,
            )
        except ErroDeRelacionamento as erro:
            messages.error(request, str(erro))
        else:
            messages.success(request, "Desfecho registrado.")
        return redirect("relacionamento:retencao")


class DetalheDoRiscoView(PainelMixin, DetailView):
    """A conta aberta do risco de um aluno."""

    modulo = Modulo.RETENCAO
    template_name = "relacionamento/risco_detalhe.html"
    context_object_name = "perfil"

    def get_queryset(self):
        return PerfilDeRisco.objects.filter(rede=self.request.rede).select_related("aluno")
