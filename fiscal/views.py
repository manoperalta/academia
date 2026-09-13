"""Telas fiscais: configuracao, notas, PDF e cancelamento."""

from __future__ import annotations

from django.contrib import messages
from django.http import HttpResponse, HttpResponseNotFound
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import DetailView, ListView, TemplateView

from fiscal import servicos
from fiscal.models import ConfiguracaoFiscal, EventoFiscal, NotaFiscal
from fiscal.servicos import ErroFiscal
from gestao.mixins import EdicaoMixin, PainelMixin
from gestao.permissoes import Modulo


def _notas(request):
    return NotaFiscal.objects.filter(rede=request.rede).select_related("aluno", "unidade")


class PainelFiscalView(PainelMixin, TemplateView):
    modulo = Modulo.FISCAL
    template_name = "fiscal/painel.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["resumo"] = servicos.resumo_fiscal(self.request.rede)
        contexto["configuracao"] = ConfiguracaoFiscal.objects.filter(rede=self.request.rede).first()
        contexto["regimes"] = ConfiguracaoFiscal.Regime.choices
        contexto["provedores"] = ConfiguracaoFiscal.Provedor.choices
        contexto["ultimas"] = _notas(self.request)[:10]
        return contexto


class SalvarConfiguracaoView(EdicaoMixin, View):
    modulo = Modulo.FISCAL

    def post(self, request, *args, **kwargs):
        try:
            servicos.configurar_fiscal(
                rede=request.rede,
                regime=request.POST.get("regime") or "simples",
                municipio=request.POST.get("municipio", ""),
                inscricao_municipal=request.POST.get("inscricao_municipal", ""),
                codigo_do_servico=request.POST.get("codigo_do_servico") or "6.01",
                aliquota_iss=request.POST.get("aliquota_iss") or 0,
                provedor=request.POST.get("provedor") or "simulado",
                retem_pis_cofins_csll=request.POST.get("retem_pis_cofins_csll") == "on",
                retem_ir=request.POST.get("retem_ir") == "on",
                retem_inss=request.POST.get("retem_inss") == "on",
                emissao_automatica=request.POST.get("emissao_automatica") == "on",
            )
        except ErroFiscal as erro:
            messages.error(request, str(erro))
        else:
            messages.success(request, "Configuracao fiscal salva.")
        return redirect("fiscal:painel")


class NotasFiscaisView(PainelMixin, ListView):
    modulo = Modulo.FISCAL
    template_name = "fiscal/notas.html"
    context_object_name = "notas"
    paginate_by = 50

    def get_queryset(self):
        consulta = _notas(self.request)
        situacao = self.request.GET.get("situacao", "").strip()
        if situacao:
            consulta = consulta.filter(situacao=situacao)
        return consulta

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["situacoes"] = NotaFiscal.Situacao.choices
        contexto["filtro"] = self.request.GET.get("situacao", "")
        return contexto


class NotaDetalheView(PainelMixin, DetailView):
    modulo = Modulo.FISCAL
    template_name = "fiscal/nota.html"
    context_object_name = "nota"

    def get_queryset(self):
        return _notas(self.request)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["eventos"] = self.object.eventos.all()
        contexto["memoria"] = [
            evento.detalhe for evento in self.object.eventos.filter(tipo=EventoFiscal.Tipo.CRIADA)
        ]
        return contexto


class BaixarNotaView(PainelMixin, View):
    modulo = Modulo.FISCAL

    def get(self, request, pk: int, *args, **kwargs):
        nota = get_object_or_404(_notas(request), pk=pk)
        conteudo = servicos.pdf_da_nota(nota)
        if not conteudo:
            return HttpResponseNotFound("Nao consegui gerar o PDF.")
        resposta = HttpResponse(conteudo, content_type="application/pdf")
        resposta["Content-Disposition"] = f'inline; filename="nota-{nota.numero or nota.pk}.pdf"'
        return resposta


class EmitirLoteView(EdicaoMixin, View):
    modulo = Modulo.FISCAL

    def post(self, request, *args, **kwargs):
        from django.utils import timezone

        simulacao = request.POST.get("dry_run") in {"1", "true", "on"}
        try:
            resultado = servicos.emitir_notas_da_competencia(
                request.rede, timezone.localdate().replace(day=1), dry_run=simulacao
            )
        except ErroFiscal as erro:
            messages.error(request, str(erro))
            return redirect("fiscal:painel")
        return render(request, "fiscal/lote.html", {"resultado": resultado})


class CancelarNotaView(EdicaoMixin, View):
    modulo = Modulo.FISCAL

    def post(self, request, pk: int, *args, **kwargs):
        nota = get_object_or_404(_notas(request), pk=pk)
        try:
            servicos.cancelar_nota(nota, request.POST.get("motivo", ""))
        except ErroFiscal as erro:
            messages.error(request, str(erro))
        else:
            messages.success(request, "Nota cancelada.")
        return redirect("fiscal:nota", pk=nota.pk)


class EmitirNotaAvulsaView(EdicaoMixin, View):
    """Nota de um pagamento especifico (o caso comum: mensalidade recebida hoje)."""

    modulo = Modulo.FISCAL

    def post(self, request, *args, **kwargs):
        from financeiro.models import Pagamento

        pagamento = Pagamento.todos.filter(
            pk=request.POST.get("pagamento"), rede=request.rede
        ).first()
        if pagamento is None:
            messages.error(request, "Pagamento nao encontrado nesta rede.")
            return redirect("fiscal:painel")
        try:
            nota = servicos.emitir_nota(
                rede=request.rede,
                valor=pagamento.valor_pago,
                competencia=pagamento.data_inicio,
                aluno=servicos._aluno_do_pagamento(pagamento),
                unidade=pagamento.unidade,
                pagamento=pagamento,
            )
        except ErroFiscal as erro:
            messages.error(request, str(erro))
            return redirect("fiscal:painel")
        messages.success(
            request, f"Nota {nota.numero} registrada ({nota.get_situacao_display().lower()})."
        )
        return redirect("fiscal:nota", pk=nota.pk)
