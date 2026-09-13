"""Telas e integracoes da cobranca recorrente."""

from __future__ import annotations

import json

from django.conf import settings
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import ListView, TemplateView

from cobranca import servicos
from cobranca.models import AutorizacaoDeDebito, CobrancaRecorrente
from cobranca.servicos import ErroDeCobranca
from gestao.mixins import EdicaoMixin, PainelMixin
from gestao.permissoes import Modulo
from usuarios.models import Usuario


def _cobrancas(request):
    return CobrancaRecorrente.objects.filter(rede=request.rede).select_related(
        "aluno", "unidade", "autorizacao", "pagamento"
    )


class PainelDeCobrancaView(PainelMixin, TemplateView):
    modulo = Modulo.COBRANCA
    template_name = "cobranca/painel.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["resumo"] = servicos.resumo_da_cobranca(self.request.rede)
        contexto["fila"] = servicos.fila_da_regua(self.request.rede)
        contexto["alunos"] = Usuario.todos.filter(rede=self.request.rede, status_user="Ativo")[:200]
        return contexto


class InadimplenciaView(PainelMixin, TemplateView):
    """Quem esta devendo, ha quantos dias, quanto e o que a regua ja fez."""

    modulo = Modulo.COBRANCA
    template_name = "cobranca/inadimplencia.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto.update(servicos.resumo_da_inadimplencia(self.request.rede))
        faixa = self.request.GET.get("faixa", "").strip()
        contexto["lista"] = servicos.lista_de_inadimplentes(self.request.rede, faixa=faixa)
        contexto["faixas"] = servicos.FAIXAS_DE_ATRASO
        contexto["filtro"] = faixa
        return contexto


class CobrancasView(PainelMixin, ListView):
    modulo = Modulo.COBRANCA
    template_name = "cobranca/lista.html"
    context_object_name = "cobrancas"
    paginate_by = 50

    def get_queryset(self):
        consulta = _cobrancas(self.request)
        situacao = self.request.GET.get("situacao", "").strip()
        if situacao:
            consulta = consulta.filter(situacao=situacao)
        return consulta

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["situacoes"] = CobrancaRecorrente.Situacao.choices
        contexto["filtro"] = self.request.GET.get("situacao", "")
        return contexto


class GerarCobrancasView(EdicaoMixin, View):
    modulo = Modulo.COBRANCA

    def post(self, request, *args, **kwargs):
        from django.utils import timezone

        simulacao = request.POST.get("dry_run") in {"1", "true", "on"}
        try:
            dia = int(request.POST.get("dia_do_vencimento") or 10)
        except ValueError:
            dia = 10
        resultado = servicos.gerar_cobrancas_do_mes(
            request.rede,
            timezone.localdate().replace(day=1),
            dia_do_vencimento=dia,
            dry_run=simulacao,
        )
        return render(request, "cobranca/geracao.html", {"resultado": resultado})


class AutorizacoesView(PainelMixin, TemplateView):
    modulo = Modulo.COBRANCA
    template_name = "cobranca/autorizacoes.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["autorizacoes"] = AutorizacaoDeDebito.objects.filter(
            rede=self.request.rede
        ).select_related("aluno")
        contexto["alunos"] = Usuario.todos.filter(rede=self.request.rede)[:200]
        contexto["modalidades"] = AutorizacaoDeDebito.Modalidade.choices
        return contexto


class AutorizarDebitoView(EdicaoMixin, View):
    modulo = Modulo.COBRANCA

    def post(self, request, *args, **kwargs):
        aluno = Usuario.todos.filter(pk=request.POST.get("aluno"), rede=request.rede).first()
        if aluno is None:
            messages.error(request, "Escolha o aluno da autorizacao.")
            return redirect("cobranca:autorizacoes")
        try:
            autorizacao = servicos.autorizar_debito(
                aluno=aluno,
                modalidade=request.POST.get("modalidade") or "pix_automatico",
                chave_pix=request.POST.get("chave_pix", ""),
                criada_por=request.user,
            )
        except ErroDeCobranca as erro:
            messages.error(request, str(erro))
        else:
            servicos.ativar_autorizacao(autorizacao, identificador_no_banco="MANUAL-ATIVACAO")
            messages.success(request, "Autorizacao criada e ativada.")
        return redirect("cobranca:autorizacoes")


class AtivarAutorizacaoView(EdicaoMixin, View):
    modulo = Modulo.COBRANCA

    def post(self, request, pk: int, *args, **kwargs):
        autorizacao = get_object_or_404(
            AutorizacaoDeDebito.objects.filter(rede=request.rede), pk=pk
        )
        try:
            servicos.ativar_autorizacao(autorizacao, request.POST.get("identificador", ""))
        except ErroDeCobranca as erro:
            messages.error(request, str(erro))
        else:
            messages.success(request, "Autorizacao ativada.")
        return redirect("cobranca:autorizacoes")


class CancelarAutorizacaoView(EdicaoMixin, View):
    modulo = Modulo.COBRANCA

    def post(self, request, pk: int, *args, **kwargs):
        autorizacao = get_object_or_404(
            AutorizacaoDeDebito.objects.filter(rede=request.rede), pk=pk
        )
        servicos.cancelar_autorizacao(autorizacao, request.POST.get("motivo", ""))
        messages.success(request, "Autorizacao cancelada e cobrancas em aberto canceladas.")
        return redirect("cobranca:autorizacoes")


class EnviarCobrancaView(EdicaoMixin, View):
    modulo = Modulo.COBRANCA

    def post(self, request, pk: int, *args, **kwargs):
        cobranca = get_object_or_404(_cobrancas(request), pk=pk)
        try:
            servicos.enviar_cobranca(cobranca)
        except ErroDeCobranca as erro:
            messages.error(request, str(erro))
        else:
            messages.success(
                request, f"Cobranca enviada (identificador {cobranca.identificador_no_banco})."
            )
        return redirect("cobranca:lista")


class LembreteView(EdicaoMixin, View):
    modulo = Modulo.COBRANCA

    def post(self, request, pk: int, *args, **kwargs):
        cobranca = get_object_or_404(_cobrancas(request), pk=pk)
        servicos.registrar_lembrete(cobranca, request.POST.get("mensagem", ""))
        messages.success(request, "Lembrete registrado no histórico da cobrança.")
        return redirect("cobranca:painel")


class CancelarCobrancaView(EdicaoMixin, View):
    modulo = Modulo.COBRANCA

    def post(self, request, pk: int, *args, **kwargs):
        cobranca = get_object_or_404(_cobrancas(request), pk=pk)
        cobranca.situacao = CobrancaRecorrente.Situacao.CANCELADA
        cobranca.save(update_fields=["situacao"])
        messages.success(request, "Cobranca cancelada.")
        return redirect("cobranca:lista")


class RetornoEmLoteView(EdicaoMixin, View):
    modulo = Modulo.COBRANCA

    def post(self, request, *args, **kwargs):
        enviado = request.FILES.get("arquivo")
        conteudo = (
            enviado.read().decode("utf-8", "replace")
            if enviado
            else request.POST.get("conteudo", "")
        )
        try:
            resultado = servicos.processar_retornos_em_lote(request.rede, conteudo)
        except ErroDeCobranca as erro:
            messages.error(request, str(erro))
        else:
            messages.success(
                request,
                f"{resultado['aplicados']} retorno(s) aplicado(s); "
                f"{resultado['ignorados']} ignorado(s).",
            )
        return redirect("cobranca:painel")


@method_decorator(csrf_exempt, name="dispatch")
class WebhookDeCobrancaView(View):
    """Retorno do PSP. Sem token configurado, recusa — nada de endpoint aberto."""

    def post(self, request, *args, **kwargs):
        import hmac

        esperado = str(getattr(settings, "COBRANCA_WEBHOOK_TOKEN", "") or "")
        recebido = request.headers.get("X-Token", "")
        if not esperado:
            return JsonResponse({"erro": "webhook sem token configurado na rede"}, status=503)
        if not hmac.compare_digest(recebido, esperado):
            return JsonResponse({"erro": "token invalido"}, status=403)
        try:
            dados = json.loads(request.body or b"{}")
        except json.JSONDecodeError:
            return JsonResponse({"erro": "corpo invalido"}, status=400)
        cobranca = CobrancaRecorrente.objects.filter(pk=dados.get("cobranca")).first()
        if cobranca is None:
            return JsonResponse({"erro": "cobranca nao encontrada"}, status=404)
        try:
            resultado = servicos.processar_retorno(
                cobranca, dados.get("situacao", ""), dados, motivo=dados.get("motivo", "")
            )
        except ErroDeCobranca as erro:
            return JsonResponse({"erro": str(erro)}, status=400)
        return JsonResponse({"ok": True, **resultado})
