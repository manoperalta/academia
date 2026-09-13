"""Painel da plataforma (SafeStack): tenants, pacotes, cobranca, regua e suporte."""

from __future__ import annotations

import csv
import uuid
from pathlib import Path

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import DetailView, ListView, TemplateView

from api.auditoria import registrar
from core.models import Rede
from core.papeis import StatusRede
from plataforma.forms import (
    ConfiguracaoPlataformaForm,
    FaturaManualForm,
    ImpersonarForm,
    PacoteForm,
    TenantEdicaoForm,
    TenantForm,
)
from plataforma.mixins import PlataformaMixin
from plataforma.models import (
    Assinatura,
    ConfiguracaoPlataforma,
    EventoCobranca,
    EventoGateway,
    Fatura,
    Impersonacao,
    Pacote,
    StatusFatura,
)
from plataforma.servicos import _reativar_rede as reativar_rede
from plataforma.servicos import (
    assinatura_da,
    emitir_cobranca_da_fatura,
    gerar_fatura,
    impersonar,
    metricas,
    processar_evento_gateway,
    provisionar_tenant,
    situacao_do_tenant,
    uso_do_tenant,
)


# ------------------------------------------------------------------ METRICAS
class MetricasView(PlataformaMixin, TemplateView):
    template_name = "plataforma/metricas.html"
    titulo = "Painel da plataforma"
    subtitulo = "Receita, clientes e cobranca"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        dados = metricas()
        contexto.update(
            dados,
            faturas_abertas=Fatura.objects.filter(
                status__in=[StatusFatura.ABERTA, StatusFatura.VENCIDA]
            )
            .select_related("rede")
            .order_by("vencimento")[:10],
            ultimos_eventos=EventoCobranca.objects.select_related("rede")[:8],
            proximos_vencimentos=Assinatura.objects.select_related("rede", "pacote")
            .filter(cancelada_em__isnull=True)
            .order_by("renovacao_em")[:8],
            modo_simulado=ConfiguracaoPlataforma.obter().gateway_em_modo_simulado,
        )
        return contexto


# ------------------------------------------------------------------ TENANTS
class TenantsView(PlataformaMixin, ListView):
    model = Rede
    template_name = "plataforma/tenants.html"
    paginate_by = 20
    titulo = "Clientes (tenants)"
    subtitulo = "Quem usa a plataforma, com qual pacote e quanto consome"

    def get_queryset(self):
        consulta = Rede.todos.select_related("assinatura__pacote").order_by("nome")
        status = self.request.GET.get("status")
        pacote = self.request.GET.get("pacote")
        termo = self.request.GET.get("q", "").strip()
        if status:
            consulta = consulta.filter(status=status)
        if pacote:
            consulta = consulta.filter(assinatura__pacote_id=pacote)
        if termo:
            from django.db.models import Q

            consulta = consulta.filter(Q(nome__icontains=termo) | Q(slug__icontains=termo))
        return consulta

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        linhas = []
        for rede in contexto["object_list"]:
            assinatura = assinatura_da(rede)
            linhas.append(
                {
                    "rede": rede,
                    "assinatura": assinatura,
                    "pacote": getattr(assinatura, "pacote", None),
                    "uso": uso_do_tenant(rede),
                    "situacao": situacao_do_tenant(rede),
                    "mrr": assinatura.valor_do_ciclo() if assinatura else 0,
                }
            )
        contexto.update(
            linhas=linhas,
            pacotes=Pacote.objects.all(),
            status_disponiveis=StatusRede.choices,
            filtro_status=self.request.GET.get("status", ""),
            filtro_pacote=self.request.GET.get("pacote", ""),
            termo=self.request.GET.get("q", ""),
        )
        return contexto


class TenantCriarView(PlataformaMixin, View):
    titulo = "Novo cliente"

    def get(self, request):
        return render(
            request,
            "plataforma/tenant_form.html",
            {
                "plataforma": True,
                "titulo": self.titulo,
                "form": TenantForm(),
                "impersonacao": None,
            },
        )

    def post(self, request):
        form = TenantForm(request.POST)
        if not form.is_valid():
            return render(
                request,
                "plataforma/tenant_form.html",
                {
                    "plataforma": True,
                    "titulo": self.titulo,
                    "form": form,
                    "impersonacao": None,
                },
            )
        dados = form.cleaned_data
        dono = None
        if dados.get("dono_email"):
            dono = get_user_model().objects.filter(email__iexact=dados["dono_email"]).first()
            if dono is None:
                messages.warning(
                    request,
                    f"Nao existe conta com o e-mail {dados['dono_email']}; o vinculo podera ser "
                    "criado depois por convite.",
                )
        rede, _assinatura = provisionar_tenant(
            nome=dados["nome"],
            slug=dados["slug"],
            pacote=dados["pacote"],
            ciclo=dados["ciclo"],
            cnpj=dados.get("cnpj", ""),
            email=dados.get("email", ""),
            telefone=dados.get("telefone", ""),
            dominio=dados.get("dominio", ""),
            trial=dados.get("trial", False),
            usuario_dono=dono,
        )
        registrar(
            "criar",
            "rede",
            entidade_id=rede.pk,
            descricao=f"Tenant {rede.nome} criado pelo painel da plataforma",
            request=request,
        )
        messages.success(request, f"Cliente {rede.nome} criado.")
        return redirect("plataforma:tenant_ficha", pk=rede.pk)


class TenantFichaView(PlataformaMixin, DetailView):
    model = Rede
    template_name = "plataforma/tenant_ficha.html"
    titulo = "Ficha do cliente"

    def get_queryset(self):
        return Rede.todos.all()

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        rede = self.object
        contexto.update(
            situacao=situacao_do_tenant(rede),
            assinatura=assinatura_da(rede),
            faturas=Fatura.objects.filter(rede=rede).order_by("-vencimento")[:20],
            assinaturas_pacotes=Pacote.objects.filter(ativo=True),
            eventos=EventoCobranca.objects.filter(rede=rede)[:10],
            impersonacoes=Impersonacao.objects.filter(rede=rede)[:10],
            form_impersonar=ImpersonarForm(),
            form_fatura=FaturaManualForm(),
        )
        return contexto


class TenantEditarView(PlataformaMixin, View):
    titulo = "Editar cliente"

    def _contexto(self, request, rede, form):
        return {
            "plataforma": True,
            "titulo": self.titulo,
            "subtitulo": str(rede),
            "rede": rede,
            "form": form,
            "impersonacao": None,
        }

    def _form(self, rede, dados=None):
        assinatura = assinatura_da(rede)
        inicial = {
            "nome": rede.nome,
            "cnpj": rede.cnpj,
            "email_responsavel": rede.email_responsavel,
            "telefone": rede.telefone,
            "dominio": rede.dominio,
            "observacoes_internas": rede.observacoes_internas,
            "pacote": getattr(assinatura, "pacote_id", None),
            "ciclo": getattr(assinatura, "ciclo", "mensal"),
            "limite_alunos_custom": getattr(assinatura, "limite_alunos_custom", None),
            "limite_professores_custom": getattr(assinatura, "limite_professores_custom", None),
            "limite_unidades_custom": getattr(assinatura, "limite_unidades_custom", None),
            "motivo_excecao": getattr(assinatura, "motivo_excecao", ""),
        }
        return TenantEdicaoForm(dados, initial=inicial)

    def get(self, request, pk):
        rede = get_object_or_404(Rede.todos, pk=pk)
        return render(
            request, "plataforma/tenant_form.html", self._contexto(request, rede, self._form(rede))
        )

    def post(self, request, pk):
        rede = get_object_or_404(Rede.todos, pk=pk)
        form = self._form(rede, request.POST)
        if not form.is_valid():
            return render(
                request, "plataforma/tenant_form.html", self._contexto(request, rede, form)
            )
        dados = form.cleaned_data
        rede.nome = dados["nome"]
        rede.cnpj = dados.get("cnpj", "")
        rede.email_responsavel = dados.get("email_responsavel", "")
        rede.telefone = dados.get("telefone", "")
        rede.dominio = dados.get("dominio", "")
        rede.observacoes_internas = dados.get("observacoes_internas", "")
        rede.save()
        assinatura = assinatura_da(rede)
        if assinatura is not None:
            if assinatura.pacote_id != dados["pacote"].pk:
                assinatura.trocar_pacote(dados["pacote"], ciclo=dados["ciclo"])
            assinatura.ciclo = dados["ciclo"]
            assinatura.limite_alunos_custom = dados.get("limite_alunos_custom")
            assinatura.limite_professores_custom = dados.get("limite_professores_custom")
            assinatura.limite_unidades_custom = dados.get("limite_unidades_custom")
            assinatura.motivo_excecao = dados.get("motivo_excecao", "")
            if any(
                [
                    dados.get("limite_alunos_custom"),
                    dados.get("limite_professores_custom"),
                    dados.get("limite_unidades_custom"),
                ]
            ):
                assinatura.autorizado_por = request.user
            assinatura.save()
        registrar(
            "alterar",
            "rede",
            entidade_id=rede.pk,
            descricao=f"Cliente {rede.nome} editado pela plataforma",
            request=request,
        )
        messages.success(request, "Cliente atualizado.")
        return redirect("plataforma:tenant_ficha", pk=rede.pk)


class TenantAcaoView(PlataformaMixin, View):
    """Suspender, reativar ou cancelar (RF-PLT-004)."""

    acoes = {
        "suspender": (StatusRede.SUSPENSO, "Cliente suspenso."),
        "reativar": (StatusRede.ATIVO, "Cliente reativado."),
        "cancelar": (StatusRede.CANCELADO, "Cliente cancelado."),
        "somente_leitura": (StatusRede.SOMENTE_LEITURA, "Cliente em somente leitura."),
    }

    def post(self, request, pk, acao):
        if acao not in self.acoes:
            messages.error(request, "Acao desconhecida.")
            return redirect("plataforma:tenant_ficha", pk=pk)
        rede = get_object_or_404(Rede.todos, pk=pk)
        novo_status, aviso = self.acoes[acao]
        rede.status = novo_status
        rede.save(update_fields=["status"])
        if acao == "cancelar":
            assinatura = assinatura_da(rede)
            if assinatura is not None and not assinatura.cancelada:
                assinatura.cancelada_em = timezone.localdate()
                assinatura.save(update_fields=["cancelada_em", "atualizado_em"])
        registrar(
            acao,
            "rede",
            entidade_id=rede.pk,
            descricao=f"Cliente {rede.nome}: {aviso}",
            request=request,
        )
        messages.success(request, aviso)
        return redirect("plataforma:tenant_ficha", pk=rede.pk)


# ------------------------------------------------------------------ PACOTES
class PacotesView(PlataformaMixin, ListView):
    model = Pacote
    template_name = "plataforma/pacotes.html"
    titulo = "Pacotes"
    subtitulo = "Prata, Bronze, Ouro e o que cada um liga"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["assinaturas_por_pacote"] = {
            pacote.pk: Assinatura.objects.filter(pacote=pacote, cancelada_em__isnull=True).count()
            for pacote in contexto["object_list"]
        }
        return contexto


class PacoteCriarView(PlataformaMixin, View):
    titulo = "Novo pacote"

    def get(self, request):
        return render(
            request,
            "plataforma/pacote_form.html",
            {"plataforma": True, "titulo": self.titulo, "form": PacoteForm(), "impersonacao": None},
        )

    def post(self, request):
        form = PacoteForm(request.POST)
        if not form.is_valid():
            return render(
                request,
                "plataforma/pacote_form.html",
                {"plataforma": True, "titulo": self.titulo, "form": form, "impersonacao": None},
            )
        pacote = form.save()
        registrar(
            "criar",
            "pacote",
            entidade_id=pacote.pk,
            descricao=f"Pacote {pacote.nome} criado",
            request=request,
        )
        messages.success(request, f"Pacote {pacote.nome} criado.")
        return redirect("plataforma:pacotes")


class PacoteEditarView(PlataformaMixin, View):
    titulo = "Editar pacote"

    def get(self, request, pk):
        pacote = get_object_or_404(Pacote, pk=pk)
        return render(
            request,
            "plataforma/pacote_form.html",
            {
                "plataforma": True,
                "titulo": self.titulo,
                "subtitulo": pacote.nome,
                "form": PacoteForm(instance=pacote),
                "impersonacao": None,
            },
        )

    def post(self, request, pk):
        pacote = get_object_or_404(Pacote, pk=pk)
        form = PacoteForm(request.POST, instance=pacote)
        if not form.is_valid():
            return render(
                request,
                "plataforma/pacote_form.html",
                {
                    "plataforma": True,
                    "titulo": self.titulo,
                    "form": form,
                    "impersonacao": None,
                },
            )
        pacote = form.save()
        registrar(
            "alterar",
            "pacote",
            entidade_id=pacote.pk,
            descricao=f"Pacote {pacote.nome} alterado",
            request=request,
        )
        messages.success(request, "Pacote atualizado.")
        return redirect("plataforma:pacotes")


# ------------------------------------------------------------------ FATURAS
class FaturasView(PlataformaMixin, ListView):
    model = Fatura
    template_name = "plataforma/faturas.html"
    paginate_by = 30
    titulo = "Faturas"
    subtitulo = "Previsto, recebido e inadimplencia"

    def get_queryset(self):
        consulta = Fatura.objects.select_related("rede", "assinatura").order_by("-vencimento")
        status = self.request.GET.get("status")
        termo = self.request.GET.get("q", "").strip()
        if status:
            consulta = consulta.filter(status=status)
        if termo:
            from django.db.models import Q

            consulta = consulta.filter(Q(numero__icontains=termo) | Q(rede__nome__icontains=termo))
        return consulta

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto.update(
            status_disponiveis=StatusFatura.choices,
            filtro_status=self.request.GET.get("status", ""),
            termo=self.request.GET.get("q", ""),
        )
        return contexto


class FaturaEmitirView(PlataformaMixin, View):
    """Gera a fatura do ciclo agora e emite a cobranca no gateway."""

    def post(self, request, pk):
        rede = get_object_or_404(Rede.todos, pk=pk)
        assinatura = assinatura_da(rede)
        if assinatura is None:
            messages.error(request, "Este cliente nao tem assinatura.")
            return redirect("plataforma:tenant_ficha", pk=rede.pk)
        if request.POST.get("valor"):
            form = FaturaManualForm(request.POST)
            if not form.is_valid():
                messages.error(request, "Confira os dados da fatura avulsa.")
                return redirect("plataforma:tenant_ficha", pk=rede.pk)
            dados = form.cleaned_data
            fatura = Fatura.objects.create(
                rede=rede,
                assinatura=assinatura,
                periodo_inicio=timezone.localdate(),
                periodo_fim=timezone.localdate(),
                vencimento=dados["vencimento"],
                valor=dados["valor"],
                desconto=dados["desconto"],
                valor_final=dados["valor"] - dados["desconto"],
                observacao=dados["descricao"],
            )
            messages.success(request, f"Fatura avulsa {fatura.numero} criada.")
        else:
            fatura = gerar_fatura(assinatura, vencimento=timezone.localdate())
            if fatura is None:
                messages.info(request, "Ja existe fatura para este ciclo.")
                return redirect("plataforma:tenant_ficha", pk=rede.pk)
            messages.success(request, f"Fatura {fatura.numero} gerada.")
        emitir_cobranca_da_fatura(fatura)
        registrar(
            "cobrar",
            "fatura",
            entidade_id=fatura.pk,
            descricao=f"Fatura {fatura.numero} emitida pela plataforma",
            request=request,
        )
        return redirect("plataforma:tenant_ficha", pk=rede.pk)


class FaturaBaixarView(PlataformaMixin, View):
    """Baixa manual (dinheiro/Pix recebido fora do gateway)."""

    def post(self, request, pk):
        fatura = get_object_or_404(Fatura.objects.select_related("rede"), pk=pk)
        mudou = fatura.marcar_paga(quando=timezone.localdate())
        registrar(
            "receber",
            "fatura",
            entidade_id=fatura.pk,
            descricao=f"Baixa manual da fatura {fatura.numero}",
            request=request,
        )
        if mudou:
            reativar_rede(fatura.rede)
            messages.success(request, f"Fatura {fatura.numero} baixada e cliente reativado.")
        else:
            messages.info(request, "A fatura ja estava paga.")
        return redirect(request.POST.get("voltar") or "plataforma:faturas")


class FaturaCancelarView(PlataformaMixin, View):
    def post(self, request, pk):
        fatura = get_object_or_404(Fatura, pk=pk)
        fatura.cancelar(motivo=request.POST.get("motivo", "cancelada pela plataforma"))
        registrar(
            "cancelar",
            "fatura",
            entidade_id=fatura.pk,
            descricao=f"Fatura {fatura.numero} cancelada",
            request=request,
        )
        messages.success(request, f"Fatura {fatura.numero} cancelada.")
        return redirect("plataforma:faturas")


class FaturaEmitirCobrancaView(PlataformaMixin, View):
    def post(self, request, pk):
        fatura = get_object_or_404(Fatura.objects.select_related("rede"), pk=pk)
        emitir_cobranca_da_fatura(fatura)
        messages.success(request, f"Cobranca emitida para a fatura {fatura.numero}.")
        return redirect(request.POST.get("voltar") or "plataforma:faturas")


class FaturaSimularPagamentoView(PlataformaMixin, View):
    """Simula o webhook do gateway (demonstracao e teste manual, sem dinheiro real)."""

    def post(self, request, pk):
        fatura = get_object_or_404(Fatura.objects.select_related("rede"), pk=pk)
        identificador = fatura.gateway_id or f"sim-{fatura.numero}"
        if not fatura.gateway_id:
            emitir_cobranca_da_fatura(fatura)
            identificador = fatura.gateway_id or identificador
        payload = {
            "id": f"evt-sim-{uuid.uuid4().hex[:12]}",
            "event": "PAYMENT_RECEIVED",
            "payment": {
                "id": identificador,
                "status": "RECEIVED",
                "value": float(fatura.valor_final),
                "externalReference": fatura.numero,
            },
        }
        evento, processado = processar_evento_gateway(payload, gateway="simulado")
        messages.success(
            request,
            f"Pagamento simulado processado: {evento.resultado}"
            if processado
            else "Evento repetido: nada foi refeito.",
        )
        return redirect("plataforma:faturas")


# ------------------------------------------------------------------ REGUA
class ReguaView(PlataformaMixin, TemplateView):
    template_name = "plataforma/regua.html"
    titulo = "Regua de cobranca"
    subtitulo = "D-3, D0, D+1, D+5, D+10 e D+30 (configuravel)"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto.update(
            eventos=EventoCobranca.objects.select_related("rede", "fatura")[:60],
            configuracoes=ConfiguracaoPlataforma.obter(),
            faturas=Fatura.objects.filter(
                status__in=[StatusFatura.ABERTA, StatusFatura.VENCIDA]
            ).select_related("rede")[:40],
        )
        return contexto

    def post(self, request):
        from plataforma.servicos import aplicar_regua

        resumo = aplicar_regua()
        registrar(
            "cobrar", "regua", descricao=f"Regua executada manualmente: {resumo}", request=request
        )
        messages.success(
            request,
            f"Regua executada: {resumo['disparos']} disparos, {resumo['bloqueios']} bloqueios, "
            f"{resumo['suspensoes']} suspensoes.",
        )
        return redirect("plataforma:regua")


class WebhooksView(PlataformaMixin, TemplateView):
    template_name = "plataforma/webhooks.html"
    titulo = "Eventos do gateway"
    subtitulo = "Historico e idempotencia"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["eventos"] = EventoGateway.objects.all()[:60]
        contexto["configuracao"] = ConfiguracaoPlataforma.obter()
        return contexto


@method_decorator(csrf_exempt, name="dispatch")
class WebhookAsaasView(View):
    """Webhook do gateway: valida token e processa de forma idempotente (RF-PLT-022)."""

    gateway = "asaas"

    def post(self, request):
        import json

        from django.http import JsonResponse

        configuracao = ConfiguracaoPlataforma.obter()
        if configuracao.token_webhook:
            enviado = request.headers.get("asaas-access-token", "")
            if enviado != configuracao.token_webhook:
                return JsonResponse({"erro": "token invalido"}, status=403)
        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return JsonResponse({"erro": "payload invalido"}, status=400)
        try:
            evento, processado = processar_evento_gateway(payload, gateway=self.gateway)
        except ValueError as erro:
            return JsonResponse({"erro": str(erro)}, status=400)
        return JsonResponse(
            {
                "recebido": True,
                "evento": evento.evento_id,
                "processado": processado,
                "resultado": evento.resultado,
            },
            status=200,
        )


# ------------------------------------------------------------------ RELATORIO
class RelatorioFinanceiroView(PlataformaMixin, TemplateView):
    template_name = "plataforma/relatorio.html"
    titulo = "Relatorio financeiro"
    subtitulo = "Recebido x previsto e inadimplencia por cliente"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        hoje = timezone.localdate()
        inicio_mes = hoje.replace(day=1)
        contexto.update(
            dados=metricas(),
            recebido_mes=Fatura.objects.filter(status=StatusFatura.PAGA, pago_em__gte=inicio_mes),
            abertas=Fatura.objects.filter(status__in=[StatusFatura.ABERTA, StatusFatura.VENCIDA])
            .select_related("rede")
            .order_by("vencimento"),
        )
        return contexto


class RelatorioFinanceiroCsvView(PlataformaMixin, View):
    def get(self, request):
        resposta = HttpResponse(content_type="text/csv; charset=utf-8")
        resposta["Content-Disposition"] = 'attachment; filename="plataforma_faturas.csv"'
        resposta.write("\ufeff")
        escritor = csv.writer(resposta, delimiter=";")
        escritor.writerow(
            ["Numero", "Cliente", "Periodo", "Vencimento", "Valor", "Status", "Pago em", "Forma"]
        )
        for fatura in Fatura.objects.select_related("rede").order_by("-vencimento"):
            escritor.writerow(
                [
                    fatura.numero,
                    fatura.rede.nome,
                    f"{fatura.periodo_inicio} a {fatura.periodo_fim}",
                    fatura.vencimento,
                    fatura.valor_final,
                    fatura.get_status_display(),
                    fatura.pago_em or "",
                    fatura.forma_pagamento,
                ]
            )
        registrar(
            "exportar",
            "fatura",
            descricao="Exportacao CSV de faturas da plataforma",
            request=request,
        )
        return resposta


# ------------------------------------------------------------------ SUPORTE
class ImpersonarView(PlataformaMixin, View):
    def post(self, request, pk):
        rede = get_object_or_404(Rede.todos, pk=pk)
        form = ImpersonarForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Informe o motivo do acesso de suporte.")
            return redirect("plataforma:tenant_ficha", pk=rede.pk)
        registro = impersonar(
            request.user,
            rede,
            form.cleaned_data["motivo"],
            request=request,
            usuario_alvo=form.cleaned_data.get("usuario_alvo", ""),
        )
        messages.info(request, f"Acesso de suporte iniciado ({registro.motivo[:80]}).")
        return redirect("gestao:visao_geral")


class SairImpersonacaoView(View):
    def post(self, request):
        from plataforma.servicos import encerrar_impersonacao

        registro = encerrar_impersonacao(request)
        if registro is None:
            messages.info(request, "Nao havia acesso de suporte em andamento.")
        else:
            messages.success(request, "Acesso de suporte encerrado.")
        return redirect("plataforma:metricas")


# ------------------------------------------------------------------ CONFIGURACAO
class ConfiguracaoView(PlataformaMixin, View):
    titulo = "Configuracao da plataforma"

    def get(self, request):
        return render(
            request,
            "plataforma/config.html",
            {
                "plataforma": True,
                "titulo": self.titulo,
                "form": ConfiguracaoPlataformaForm(instance=ConfiguracaoPlataforma.obter()),
                "impersonacao": None,
                "configuracao": ConfiguracaoPlataforma.obter(),
            },
        )

    def post(self, request):
        configuracao = ConfiguracaoPlataforma.obter()
        form = ConfiguracaoPlataformaForm(request.POST, instance=configuracao)
        if not form.is_valid():
            return render(
                request,
                "plataforma/config.html",
                {
                    "plataforma": True,
                    "titulo": self.titulo,
                    "form": form,
                    "impersonacao": None,
                    "configuracao": configuracao,
                },
            )
        form.save()
        registrar(
            "alterar",
            "configuracao_plataforma",
            entidade_id=configuracao.pk,
            descricao="Configuracao da plataforma atualizada",
            request=request,
        )
        messages.success(request, "Configuracao salva.")
        return redirect("plataforma:config")


class SaudeView(PlataformaMixin, TemplateView):
    """Observabilidade por cliente: requisicoes, erros 5xx e alertas (RNF-008)."""

    template_name = "plataforma/saude.html"
    titulo = "Saúde dos clientes"
    subtitulo = "Requisições, erros e alertas das últimas 24 horas"

    def get_context_data(self, **kwargs):
        from governanca.models import ErroTenant
        from governanca.servicos import alertas_pendentes, resumo_de_saude

        contexto = super().get_context_data(**kwargs)
        contexto.update(
            saude=resumo_de_saude(horas=24),
            alertas=alertas_pendentes(),
            erros=ErroTenant.objects.select_related("rede")[:25],
        )
        return contexto


class BackupsView(PlataformaMixin, TemplateView):
    """Backups, verificacao por restauracao de teste e exportacao por cliente (RNF-005)."""

    template_name = "plataforma/backups.html"
    titulo = "Backups"
    subtitulo = "Registro, verificação e retenção"

    def get_context_data(self, **kwargs):
        from governanca.models import RegistroBackup

        contexto = super().get_context_data(**kwargs)
        contexto.update(
            backups=RegistroBackup.objects.select_related("rede")[:40],
            ultimo=RegistroBackup.objects.filter(tipo=RegistroBackup.Tipo.BANCO)
            .order_by("-criado_em")
            .first(),
            clientes=Rede.todos.all()[:60],
        )
        return contexto


class BackupAcaoView(PlataformaMixin, View):
    """Roda um backup, verifica o ultimo, aplica retencao ou exporta um cliente."""

    def post(self, request):
        from governanca.models import RegistroBackup
        from governanca.servicos import (
            aplicar_retencao_de_backups,
            executar_backup,
            exportar_tenant,
            verificar_backup,
        )

        acao = request.POST.get("acao", "executar")
        if acao == "executar":
            registro = executar_backup()
            if registro.situacao == RegistroBackup.Situacao.OK:
                messages.success(
                    request,
                    f"Backup concluído: {Path(registro.arquivo).name} "
                    f"({registro.tamanho_mb} MB). Verificando…",
                )
                verificacao = verificar_backup(registro)
                (messages.success if verificacao["ok"] else messages.warning)(
                    request, f"Verificação: {verificacao['detalhe']}"
                )
            else:
                messages.error(request, f"Backup falhou: {registro.erro[:200]}")
        elif acao == "verificar":
            verificacao = verificar_backup()
            (messages.success if verificacao["ok"] else messages.warning)(
                request, f"Verificação: {verificacao['detalhe']}"
            )
        elif acao == "retencao":
            resultado = aplicar_retencao_de_backups(dry_run=False)
            messages.success(
                request,
                f"Retenção aplicada: {resultado['mantidos']} mantidos, "
                f"{resultado['apagados']} apagados.",
            )
        elif acao == "exportar" and request.POST.get("rede"):
            rede = get_object_or_404(Rede.todos, pk=request.POST["rede"])
            registro = exportar_tenant(rede)
            messages.success(request, f"Exportação de {rede.nome}: {Path(registro.arquivo).name}")
        registrar("backup", "plataforma", descricao=f"Ação de backup: {acao}", request=request)
        return redirect("plataforma:backups")


class DominiosView(PlataformaMixin, TemplateView):
    """Estado de endereco/certificado por cliente (RF-PLT-050..052)."""

    template_name = "plataforma/dominios.html"
    titulo = "Domínios e certificados"
    subtitulo = "Subdomínio, domínio próprio e certificado de cada cliente"

    def get_context_data(self, **kwargs):
        from governanca.servicos import estado_do_provisionamento, subdominio_da

        contexto = super().get_context_data(**kwargs)
        contexto["linhas"] = [
            {
                "rede": rede,
                "subdominio": subdominio_da(rede),
                "estado": estado_do_provisionamento(rede),
            }
            for rede in Rede.todos.all()
        ]
        return contexto


class DominioAcaoView(PlataformaMixin, View):
    """Verifica o dominio de um cliente ou marca o certificado para reemissao."""

    def post(self, request, pk):
        from governanca.servicos import reemitir_certificado, verificar_dominio

        rede = get_object_or_404(Rede.todos, pk=pk)
        acao = request.POST.get("acao", "verificar")
        resultado = (
            reemitir_certificado(rede)
            if acao == "reemitir"
            else verificar_dominio(rede, forcar=True)
        )
        (messages.success if resultado.get("ok") else messages.warning)(
            request, resultado["mensagem"]
        )
        registrar(
            "alterar",
            "dominio",
            entidade_id=rede.pk,
            descricao=f"Ação de domínio ({acao}) em {rede.nome}",
            request=request,
        )
        return redirect("plataforma:dominios")


class LgpdView(PlataformaMixin, TemplateView):
    """Visao da plataforma sobre pedidos de titulares e retencao (RNF-006)."""

    template_name = "plataforma/lgpd.html"
    titulo = "LGPD"
    subtitulo = "Pedidos de titulares, prazos e retenção"

    def get_context_data(self, **kwargs):
        from governanca.models import RegraRetencao, SolicitacaoTitular

        contexto = super().get_context_data(**kwargs)
        pedidos = list(SolicitacaoTitular.objects.select_related("rede")[:40])
        contexto.update(
            pedidos=pedidos,
            abertos=[pedido for pedido in pedidos if pedido.situacao == "aberta"],
            atrasados=[pedido for pedido in pedidos if pedido.atrasada],
            regras=RegraRetencao.objects.all(),
        )
        return contexto
