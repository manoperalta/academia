"""Telas do controle de acesso, integracao da catraca e conciliacao de parceiros."""

from __future__ import annotations

import hmac
import json

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import DetailView, ListView, TemplateView

from acesso import servicos
from acesso.models import (
    CredencialDeAcesso,
    DispositivoDeAcesso,
    ExtratoDeParceiro,
    PlanoDeParceiro,
    RegistroDeAcesso,
)
from acesso.servicos import ErroDeAcesso
from core.models import Unidade
from gestao.mixins import EdicaoMixin, PainelMixin
from gestao.permissoes import Modulo
from usuarios.models import Usuario


def _registros(request):
    return RegistroDeAcesso.objects.filter(rede=request.rede).select_related(
        "aluno", "unidade", "credencial"
    )


class PainelDeAcessoView(PainelMixin, TemplateView):
    """Quem entrou, quem foi barrado e por que."""

    modulo = Modulo.ACESSO
    template_name = "acesso/painel.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["resumo"] = servicos.resumo_do_acesso(self.request.rede)
        contexto["ultimos"] = _registros(self.request)[:25]
        contexto["unidades"] = Unidade.objects.filter(rede=self.request.rede)
        contexto["alunos"] = Usuario.todos.filter(rede=self.request.rede, status_user="Ativo")[:200]
        return contexto


class RegistrosDeAcessoView(PainelMixin, ListView):
    modulo = Modulo.ACESSO
    template_name = "acesso/registros.html"
    context_object_name = "registros"
    paginate_by = 50

    def get_queryset(self):
        consulta = _registros(self.request)
        situacao = self.request.GET.get("situacao", "").strip()
        if situacao == "liberado":
            consulta = consulta.filter(liberado=True)
        elif situacao == "negado":
            consulta = consulta.filter(liberado=False)
        return consulta

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["filtro"] = self.request.GET.get("situacao", "")
        return contexto


class LiberarManualView(EdicaoMixin, View):
    """Recepcao libera na mao, e a liberacao fica registrada como manual."""

    modulo = Modulo.ACESSO

    def post(self, request, *args, **kwargs):
        aluno = Usuario.todos.filter(pk=request.POST.get("aluno"), rede=request.rede).first()
        unidade = Unidade.objects.filter(pk=request.POST.get("unidade"), rede=request.rede).first()
        if aluno is None or unidade is None:
            messages.error(request, "Escolha o aluno e a unidade.")
            return redirect("acesso:painel")
        resultado = servicos.liberar_manualmente(
            rede=request.rede,
            unidade=unidade,
            aluno=aluno,
            motivo=request.POST.get("motivo", ""),
            liberado_por=request.user,
        )
        if resultado["liberado"]:
            messages.success(request, f"Acesso liberado para {aluno.nome}.")
        else:
            messages.error(request, f"Acesso negado: {resultado['motivo']}.")
        return redirect("acesso:painel")


class CredenciaisView(PainelMixin, ListView):
    modulo = Modulo.ACESSO
    template_name = "acesso/credenciais.html"
    context_object_name = "credenciais"
    paginate_by = 50

    def get_queryset(self):
        return CredencialDeAcesso.objects.filter(rede=self.request.rede).select_related("aluno")

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["dispositivos"] = DispositivoDeAcesso.objects.filter(
            rede=self.request.rede
        ).select_related("unidade")
        contexto["alunos"] = Usuario.todos.filter(rede=self.request.rede)[:200]
        contexto["unidades"] = Unidade.objects.filter(rede=self.request.rede)
        return contexto


class EmitirCredencialView(EdicaoMixin, View):
    modulo = Modulo.ACESSO

    def post(self, request, *args, **kwargs):
        aluno = Usuario.todos.filter(pk=request.POST.get("aluno"), rede=request.rede).first()
        if aluno is None:
            messages.error(request, "Escolha o aluno da credencial.")
            return redirect("acesso:credenciais")
        try:
            servicos.emitir_credencial(
                aluno=aluno,
                codigo=request.POST.get("codigo", ""),
                tipo=request.POST.get("tipo", "cartao"),
            )
        except ErroDeAcesso as erro:
            messages.error(request, str(erro))
        else:
            messages.success(request, "Credencial emitida.")
        return redirect("acesso:credenciais")


class CancelarCredencialView(EdicaoMixin, View):
    modulo = Modulo.ACESSO

    def post(self, request, pk: int, *args, **kwargs):
        credencial = get_object_or_404(CredencialDeAcesso.objects.filter(rede=request.rede), pk=pk)
        servicos.cancelar_credencial(credencial)
        messages.success(request, "Credencial cancelada.")
        return redirect("acesso:credenciais")


class CriarDispositivoView(EdicaoMixin, View):
    modulo = Modulo.ACESSO

    def post(self, request, *args, **kwargs):
        unidade = Unidade.objects.filter(pk=request.POST.get("unidade"), rede=request.rede).first()
        identificador = (request.POST.get("identificador") or "").strip()
        if unidade is None or not identificador:
            messages.error(request, "Informe a unidade e o identificador do equipamento.")
            return redirect("acesso:credenciais")
        token = servicos_novo_token()
        DispositivoDeAcesso.objects.update_or_create(
            identificador=identificador,
            defaults={
                "rede": request.rede,
                "unidade": unidade,
                "nome": request.POST.get("nome") or identificador,
                "tipo": request.POST.get("tipo") or "catraca",
                "token": token,
            },
        )
        messages.success(request, f"Dispositivo {identificador} cadastrado.")
        return redirect("acesso:credenciais")


def servicos_novo_token() -> str:

    import secrets

    return secrets.token_urlsafe(24)


@method_decorator(csrf_exempt, name="dispatch")
class IntegracaoDaCatracaView(View):
    """Endpoint que o equipamento chama: identificador no cabecalho e token no corpo.

    Sem sessao: a autenticacao e o token do dispositivo, comparado em tempo constante. O que o
    equipamento recebe de volta e o minimo: se abre ou nao, e o motivo quando nao abre.
    """

    def post(self, request, *args, **kwargs):
        identificador = request.headers.get("X-Dispositivo", "") or request.GET.get(
            "dispositivo", ""
        )
        dispositivo = (
            DispositivoDeAcesso.objects.filter(identificador=identificador)
            .select_related("unidade", "rede")
            .first()
        )
        if dispositivo is None:
            return JsonResponse(
                {"liberado": False, "motivo": "dispositivo desconhecido"}, status=403
            )

        try:
            dados = json.loads(request.body or b"{}")
        except json.JSONDecodeError:
            dados = {}
        token = dados.get("token") or request.headers.get("X-Token", "")
        if not hmac.compare_digest(str(token), str(dispositivo.token)):
            return JsonResponse({"liberado": False, "motivo": "token invalido"}, status=403)
        if not dispositivo.ativo:
            return JsonResponse({"liberado": False, "motivo": "dispositivo inativo"}, status=200)

        resultado = servicos.decidir_acesso(
            rede=dispositivo.rede,
            unidade=dispositivo.unidade,
            codigo=dados.get("codigo", ""),
            origem=dados.get("origem", "catraca"),
            dispositivo=dispositivo,
        )
        corpo = {
            "liberado": resultado["liberado"],
            "motivo": resultado["motivo"],
            "aluno": resultado["aluno"].nome if resultado["aluno"] else "",
            "registro": resultado["registro"].pk,
            "checkin": resultado["checkin_gerado"],
            "itinerante": resultado["registro"].itinerante,
        }
        return JsonResponse(corpo)


class ParceirosView(PainelMixin, TemplateView):
    """Planos de parceiro e os extratos do mes com a conciliacao."""

    modulo = Modulo.PARCEIROS
    template_name = "acesso/parceiros.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["planos"] = PlanoDeParceiro.objects.filter(rede=self.request.rede)
        contexto["extratos"] = ExtratoDeParceiro.objects.filter(
            rede=self.request.rede
        ).select_related("plano_de_parceiro")
        contexto["parceiros"] = PlanoDeParceiro.Parceiro.choices
        return contexto


class CriarPlanoDeParceiroView(EdicaoMixin, View):
    modulo = Modulo.PARCEIROS

    def post(self, request, *args, **kwargs):
        try:
            PlanoDeParceiro.objects.update_or_create(
                rede=request.rede,
                parceiro=request.POST.get("parceiro") or "wellhub",
                nome_no_parceiro=(request.POST.get("nome_no_parceiro") or "").strip(),
                defaults={
                    "valor_por_acesso": request.POST.get("valor_por_acesso") or 0,
                    "percentual_do_parceiro": request.POST.get("percentual") or 0,
                    "limite_de_acessos_por_mes": request.POST.get("limite") or 0,
                },
            )
        except Exception as erro:  # pragma: no cover - validacao do banco
            messages.error(request, f"Nao consegui salvar o plano: {erro}")
        else:
            messages.success(request, "Plano de parceiro salvo.")
        return redirect("acesso:parceiros")


class ImportarExtratoView(EdicaoMixin, View):
    modulo = Modulo.PARCEIROS

    def post(self, request, *args, **kwargs):

        plano = get_object_or_404(
            PlanoDeParceiro.objects.filter(rede=request.rede), pk=request.POST.get("plano")
        )
        enviado = request.FILES.get("arquivo")
        conteudo = ""
        if enviado is not None:
            conteudo = enviado.read().decode("utf-8", "replace")
            nome = enviado.name
        else:
            conteudo = request.POST.get("conteudo", "")
            nome = "colado na tela"
        competencia = _competencia(request.POST.get("competencia"))
        try:
            extrato = servicos.importar_extrato(
                plano_de_parceiro=plano,
                competencia=competencia,
                conteudo=conteudo,
                nome_do_arquivo=nome,
            )
        except ErroDeAcesso as erro:
            messages.error(request, str(erro))
            return redirect("acesso:parceiros")
        messages.success(request, f"Extrato importado com {extrato.total_de_acessos} linha(s).")
        return redirect("acesso:extrato", pk=extrato.pk)


class ConciliarExtratoView(EdicaoMixin, View):
    modulo = Modulo.PARCEIROS

    def post(self, request, pk: int, *args, **kwargs):
        extrato = get_object_or_404(ExtratoDeParceiro.objects.filter(rede=request.rede), pk=pk)
        simulacao = request.POST.get("dry_run") in {"1", "true", "on"}
        servicos.conciliar_extrato(extrato, dry_run=simulacao)
        extrato.refresh_from_db()
        messages.success(
            request, "Simulação concluída (nada gravado)." if simulacao else "Conciliação gravada."
        )
        return redirect("acesso:extrato", pk=extrato.pk)


class ExtratoDetalheView(PainelMixin, DetailView):
    modulo = Modulo.PARCEIROS
    template_name = "acesso/extrato.html"
    context_object_name = "extrato"

    def get_queryset(self):
        return ExtratoDeParceiro.objects.filter(rede=self.request.rede).select_related(
            "plano_de_parceiro"
        )

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["linhas"] = self.object.linhas.all()
        contexto["resultado"] = servicos.conciliar_extrato(self.object, dry_run=True)
        return contexto


def _competencia(valor):

    from django.utils import timezone

    if valor:
        try:
            return timezone.datetime.strptime(valor, "%Y-%m").date().replace(day=1)
        except ValueError:
            pass
    return timezone.localdate().replace(day=1)
