"""Painel da rede: consolidado, unidades, repasses, governanca, comunicados e onboarding."""
from __future__ import annotations

import csv
from datetime import date, timedelta

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView

from api.auditoria import registrar
from core.models import Unidade
from gestao.permissoes import Modulo
from gestao.views import ListaPainel, PainelMixin
from rede import forms as formularios
from rede.models import (
    Comunicado, ImplantacaoDeUnidade, LeituraDeComunicado, Meta, PoliticaDaRede, RegraDeRepasse,
    Repasse, SolicitacaoDeAprovacao, TemplateDeUnidade, TransferenciaDeAluno,
)
from rede.servicos import (
    ErroDeRede, aplicar_template, atualizar_atrasados, atualizar_metas, comparativo_entre_unidades,
    conferir_repasse, consolidado_da_rede, distribuir_catalogo, emitir_repasse, emitir_repasses_do_mes,
    encerrar_unidade, marcar_item_do_checklist, marcar_repasse_pago, periodo_do_mes, politica,
    regra_para, relatorio_de_repasses, transferir_alunos,
)

ZERO = 0


def _periodo_do_pedido(request) -> tuple[date, date]:
    """Periodo pedido na tela (ou o mes corrente)."""
    padrao_inicio, padrao_fim = periodo_do_mes()
    try:
        inicio = date.fromisoformat(request.GET.get("inicio", "") or str(padrao_inicio))
        fim = date.fromisoformat(request.GET.get("fim", "") or str(padrao_fim))
    except ValueError:
        return padrao_inicio, padrao_fim
    if fim < inicio:
        return padrao_inicio, padrao_fim
    return inicio, fim


class FormularioDaRede(PainelMixin, View):
    """Base simples para telas de formulario da rede (GET mostra, POST salva)."""

    template_name = "gestao/formulario.html"
    form_class = None
    titulo = ""
    subtitulo = ""
    sucesso_url = "rede:painel"
    mensagem_de_sucesso = "Salvo."

    def get_form(self, dados=None):
        return self.form_class(dados or None, rede=self.request.rede)

    def montar(self, formulario, contexto=None):
        base = {
            "form": formulario,
            "titulo": self.titulo,
            "subtitulo": self.subtitulo,
            "modulo": getattr(self, "modulo", None).value if getattr(self, "modulo", None) else "",
            "url_cancelar": reverse(self.sucesso_url),
        }
        base.update(contexto or {})
        return base

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self.montar(self.get_form(), self.contexto_extra()))

    def contexto_extra(self):
        return {}

    def post(self, request, *args, **kwargs):
        formulario = self.get_form(request.POST)
        if not formulario.is_valid():
            return render(request, self.template_name, self.montar(formulario, self.contexto_extra()))
        self.salvar(formulario.cleaned_data if hasattr(formulario, "cleaned_data") else None, formulario)
        messages.success(request, self.mensagem_de_sucesso)
        return redirect(self.sucesso_url)

    def salvar(self, dados, formulario):
        raise NotImplementedError


class RedePainelView(PainelMixin, TemplateView):
    """Consolidado da rede, comparativo entre unidades e pendencias (RF-RED-009/010)."""

    template_name = "rede/painel.html"
    modulo = Modulo.REDE
    titulo = "Painel da rede"
    subtitulo = "Consolidado, comparativo entre unidades e pendências"

    def get_context_data(self, **kwargs):
        inicio, fim = _periodo_do_pedido(self.request)
        rede = self.request.rede
        atualizar_metas(rede)
        contexto = super().get_context_data(**kwargs)
        contexto.update(
            inicio=inicio,
            fim=fim,
            consolidado=consolidado_da_rede(rede, inicio, fim),
            metas=list(Meta.objects.filter(rede=rede, inicio__gte=inicio, fim__lte=fim)),
            repasses_atrasados=Repasse.objects.filter(rede=rede, situacao=Repasse.Situacao.ATRASADO),
            aprovacoes_pendentes=SolicitacaoDeAprovacao.objects.filter(
                rede=rede, situacao=SolicitacaoDeAprovacao.Situacao.PENDENTE),
            comunicados_abertos=Comunicado.objects.filter(rede=rede, ativo=True)[:5],
            travas=__import__("rede.servicos", fromlist=["travas_vigentes"]).travas_vigentes(rede),
        )
        return contexto


class UnidadesView(ListaPainel):
    model = Unidade
    modulo = Modulo.UNIDADES
    titulo = "Unidades"
    colunas = [("Unidade", "nome"), ("Código", "codigo"), ("Tipo", "tipo"), ("Cidade", "cidade"),
               ("UF", "uf"), ("Status", "status")]
    campo_busca = ("nome", "codigo", "cidade")
    ordenacao = ("nome",)
    url_novo = "rede:unidade_criar"
    url_editar = "rede:unidade_editar"
    mostrar_arquivados = False

    def get_queryset(self):
        return Unidade.objects.filter(rede=self.request.rede).order_by("nome")


def pode_criar_unidade(rede) -> tuple[bool, str]:
    """Limite de unidades do pacote, com mensagem acionavel (RF-RED-021/022)."""
    from plataforma.servicos import assinatura_da

    assinatura = assinatura_da(rede)
    if assinatura is None:
        return True, ""
    limite = getattr(assinatura.pacote, "limite_unidades", None)
    if limite is None:
        return True, ""
    atuais = Unidade.objects.filter(rede=rede).exclude(status="inativa").count()
    if atuais < limite:
        return True, ""
    return False, (f"O pacote {assinatura.pacote.nome} inclui {limite} unidade(s) e você já tem {atuais}. "
                   f"Fale com a SafeStack para adicionar uma unidade ou mudar de pacote.")


class UnidadeCriarView(FormularioDaRede):
    form_class = formularios.UnidadeForm
    modulo = Modulo.UNIDADES
    titulo = "Nova unidade"
    subtitulo = "Cadastro de unidade da rede"
    sucesso_url = "rede:unidades"
    mensagem_de_sucesso = "Unidade criada."

    def get(self, request, *args, **kwargs):
        permitido, aviso = pode_criar_unidade(request.rede)
        if not permitido:
            messages.error(request, aviso)
            return redirect("rede:unidades")
        return super().get(request, *args, **kwargs)

    def salvar(self, dados, formulario):
        unidade = formulario.save(commit=False)
        unidade.rede = self.request.rede
        unidade.save()
        registrar("criar", "unidade", entidade_id=unidade.pk,
                  descricao=f"Unidade {unidade.nome} criada", request=self.request)


class UnidadeEditarView(FormularioDaRede):
    form_class = formularios.UnidadeForm
    modulo = Modulo.UNIDADES
    titulo = "Editar unidade"
    sucesso_url = "rede:unidades"
    mensagem_de_sucesso = "Unidade atualizada."

    def get_form(self, dados=None):
        unidade = get_object_or_404(Unidade, pk=self.kwargs["pk"], rede=self.request.rede)
        return self.form_class(dados or None, instance=unidade, rede=self.request.rede)

    def salvar(self, dados, formulario):
        unidade = formulario.save(commit=False)
        politica_da_rede = politica(self.request.rede)
        if (unidade.sobrescrever_branding and not politica_da_rede.permitir_sobrescrita_branding):
            unidade.sobrescrever_branding = False
            messages.warning(self.request, "A rede não permite que a unidade sobrescreva a marca "
                                           "(RF-RED-013); o kit da rede segue valendo.")
        unidade.save()
        registrar("alterar", "unidade", entidade_id=unidade.pk,
                  descricao=f"Unidade {unidade.nome} atualizada", request=self.request)


class UnidadeEncerrarView(PainelMixin, View):
    """Encerra a unidade, transferindo os alunos em lote (RF-RED-024)."""

    modulo = Modulo.UNIDADES
    nivel_minimo = "admin"

    def post(self, request, pk):
        unidade = get_object_or_404(Unidade, pk=pk, rede=request.rede)
        destino_id = request.POST.get("destino") or None
        destino = Unidade.objects.filter(pk=destino_id, rede=request.rede).first() if destino_id else None
        if (request.POST.get("confirmacao") or "").strip().upper() != "ENCERRAR":
            messages.error(request, "Para confirmar, digite ENCERRAR no campo de confirmação.")
            return redirect("rede:unidades")
        try:
            resultado = encerrar_unidade(unidade, destino, usuario=request.user)
        except ErroDeRede as erro:
            messages.error(request, str(erro))
            return redirect("rede:unidades")
        messages.success(
            request,
            f"{unidade.nome} encerrada. {resultado['transferidos']} aluno(s) transferido(s)"
            + (f" para {destino.nome}." if destino else " (sem unidade de destino)."),
        )
        return redirect("rede:unidades")


class AplicarTemplateView(PainelMixin, View):
    """Onboarding: aplica o template na unidade e controla o checklist (RF-RED-016)."""

    modulo = Modulo.UNIDADES
    nivel_minimo = "admin"
    template_name = "rede/onboarding.html"

    def get(self, request):
        implantacoes = ImplantacaoDeUnidade.objects.filter(unidade__rede=request.rede).select_related(
            "unidade", "template")
        return render(request, self.template_name, {
            "titulo": "Onboarding de unidade",
            "modulo": Modulo.UNIDADES.value,
            "unidades": Unidade.objects.filter(rede=request.rede),
            "templates": TemplateDeUnidade.objects.filter(rede=request.rede, ativo=True),
            "implantacoes": implantacoes,
        })

    def post(self, request):
        if request.POST.get("item_id"):
            implantacao = get_object_or_404(
                ImplantacaoDeUnidade, pk=request.POST.get("implantacao"), unidade__rede=request.rede)
            marcar_item_do_checklist(implantacao, int(request.POST["item_id"]),
                                     concluido=request.POST.get("concluido") == "1")
            return redirect("rede:unidade_template")
        unidade = get_object_or_404(Unidade, pk=request.POST.get("unidade"), rede=request.rede)
        template = TemplateDeUnidade.objects.filter(
            pk=request.POST.get("template") or None, rede=request.rede).first()
        implantacao = aplicar_template(unidade, template, usuario=request.user)
        messages.success(request, f"Template aplicado em {unidade.nome} "
                                  f"({implantacao.progresso}% do checklist).")
        return redirect("rede:unidade_template")


class MetasView(ListaPainel):
    model = Meta
    modulo = Modulo.REDE
    titulo = "Metas"
    colunas = [("Período", "inicio"), ("Unidade", "unidade"), ("Indicador", "indicador"),
               ("Alvo", "alvo"), ("Realizado", "realizado")]
    ordenacao = ("-inicio", "-pk")
    url_novo = "rede:meta_criar"
    mostrar_arquivados = False

    def get_queryset(self):
        atualizar_metas(self.request.rede)
        return Meta.objects.filter(rede=self.request.rede).select_related("unidade").order_by("-inicio")


class MetaCriarView(FormularioDaRede):
    form_class = formularios.MetaForm
    modulo = Modulo.REDE
    titulo = "Nova meta"
    sucesso_url = "rede:metas"
    mensagem_de_sucesso = "Meta criada."

    def salvar(self, dados, formulario):
        meta = formulario.save(commit=False)
        meta.rede = self.request.rede
        meta.save()


class RepassesView(ListaPainel):
    model = Repasse
    modulo = Modulo.REPASSES
    titulo = "Repasses e royalties"
    subtitulo = "Memória de cálculo auditável por unidade e período"
    colunas = [("Período", "inicio"), ("Unidade", "unidade"), ("Base", "base"),
               ("Base de cálculo", "base_de_calculo"), ("Devido", "valor_devido"),
               ("Pago", "valor_pago"), ("Situação", "situacao")]
    ordenacao = ("-inicio", "unidade__nome")
    url_detalhe = "rede:repasse_detalhe"
    mostrar_arquivados = False

    def get_queryset(self):
        atualizar_atrasados(self.request.rede)
        return Repasse.objects.filter(rede=self.request.rede).select_related("unidade")

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        inicio, fim = _periodo_do_pedido(self.request)
        contexto.update(relatorio=relatorio_de_repasses(self.request.rede, inicio, fim),
                        inicio=inicio, fim=fim,
                        tem_regra=RegraDeRepasse.objects.filter(rede=self.request.rede, ativo=True).exists())
        return contexto


class RepasseAcaoView(PainelMixin, View):
    """Prévia (dry-run), emissão do período e baixa de repasses."""

    modulo = Modulo.REPASSES
    nivel_minimo = "editar"

    def post(self, request):
        acao = request.POST.get("acao", "previa")
        unidades = Unidade.objects.filter(rede=request.rede, status="ativa")
        if request.POST.get("unidade"):
            unidades = unidades.filter(pk=request.POST["unidade"])
        try:
            inicio, fim = _periodo_do_pedido(request)
            if acao == "previa":
                from rede.servicos import calcular_repasse

                previas = []
                for unidade in unidades:
                    try:
                        calculo = calcular_repasse(unidade, inicio, fim)
                        previas.append({"unidade": unidade.nome, "valor": calculo["valor_devido"],
                                        "base": calculo["base_de_calculo"],
                                        "linhas": len(calculo["linhas"])})
                    except ErroDeRede as erro:
                        previas.append({"unidade": unidade.nome, "valor": None, "erro": str(erro)})
                contexto = " · ".join(
                    f"{item['unidade']}: R$ {item['valor']}" if item.get("valor") is not None
                    else f"{item['unidade']}: {item['erro']}" for item in previas
                )
                messages.info(request, f"Prévia ({inicio:%d/%m} a {fim:%d/%m}, nada gravado): {contexto}")
            elif acao == "emitir":
                resultado = emitir_repasses_do_mes(request.rede, referencia=fim)
                messages.success(
                    request,
                    f"{len(resultado['emitidos'])} repasse(s) emitido(s), total R$ {resultado['total']}."
                    + (f" {len(resultado['erros'])} unidade(s) sem regra." if resultado["erros"] else ""),
                )
            elif acao == "atrasados":
                messages.success(request, f"{atualizar_atrasados(request.rede)} repasse(s) marcado(s) "
                                          "como atrasado.")
            elif acao == "pagar":
                repasse = get_object_or_404(Repasse, pk=request.POST.get("repasse"), rede=request.rede)
                marcar_repasse_pago(repasse, request.POST.get("valor") or repasse.saldo, request.user)
                messages.success(request, f"Baixa registrada em {repasse.unidade.nome}.")
        except ErroDeRede as erro:
            messages.error(request, str(erro))
        return redirect("rede:repasses")


class RepasseDetalheView(PainelMixin, TemplateView):
    """Demonstrativo do repasse com a memória de cálculo e a conferência (RF-RED-012)."""

    template_name = "rede/repasse_detalhe.html"
    modulo = Modulo.REPASSES
    titulo = "Demonstrativo de repasse"

    def get_context_data(self, **kwargs):
        repasse = get_object_or_404(Repasse, pk=self.kwargs["pk"], rede=self.request.rede)
        contexto = super().get_context_data(**kwargs)
        contexto.update(
            repasse=repasse,
            itens=repasse.itens.all(),
            conferencia=conferir_repasse(repasse),
            regra=regra_para(repasse.unidade, referencia=repasse.fim),
        )
        return contexto


class RepasseCsvView(PainelMixin, View):
    modulo = Modulo.REPASSES

    def get(self, request, pk):
        repasse = get_object_or_404(Repasse, pk=pk, rede=request.rede)
        resposta = HttpResponse(content_type="text/csv")
        resposta["Content-Disposition"] = f'attachment; filename="repasse-{repasse.unidade.slug if hasattr(repasse.unidade, "slug") else repasse.pk}.csv"'
        escritor = csv.writer(resposta)
        escritor.writerow(["Demonstrativo de repasse", repasse.unidade.nome, f"{repasse.inicio:%d/%m/%Y} a {repasse.fim:%d/%m/%Y}"])
        escritor.writerow([])
        escritor.writerow(["Ordem", "Tipo", "Descrição", "Base", "Percentual (%)", "Valor"])
        for item in repasse.itens.all():
            escritor.writerow([item.ordem, item.get_tipo_display(), item.descricao, item.base,
                               item.percentual, item.valor])
        escritor.writerow([])
        escritor.writerow(["", "", "Total devido", "", "", repasse.valor_devido])
        escritor.writerow(["", "", "Hash do cálculo", "", "", repasse.hash_do_calculo])
        return resposta


class RegrasDeRepasseView(ListaPainel):
    model = RegraDeRepasse
    modulo = Modulo.REPASSES
    titulo = "Regras de repasse"
    subtitulo = "Percentual, base de cálculo, exclusões e piso mínimo"
    colunas = [("Unidade", "unidade"), ("Tipo", "tipo"), ("Percentual (%)", "percentual"),
               ("Base", "base"), ("Fundo (%)", "fundo_de_marketing"), ("Vencimento", "dia_de_vencimento"),
               ("Ativa", "ativo")]
    ordenacao = ("unidade__nome", "-criado_em")
    url_novo = "rede:regra_criar"
    url_editar = "rede:regra_editar"
    mostrar_arquivados = False

    def get_queryset(self):
        return RegraDeRepasse.objects.filter(rede=self.request.rede).select_related("unidade")


class RegraCriarView(FormularioDaRede):
    form_class = formularios.RegraDeRepasseForm
    modulo = Modulo.REPASSES
    titulo = "Nova regra de repasse"
    sucesso_url = "rede:regras"
    mensagem_de_sucesso = "Regra criada."

    def salvar(self, dados, formulario):
        regra = formulario.save(commit=False)
        regra.rede = self.request.rede
        regra.save()
        registrar("criar", "regra_de_repasse", entidade_id=regra.pk,
                  descricao=f"Regra de repasse criada ({regra.get_tipo_display()})", request=self.request)


class RegraEditarView(FormularioDaRede):
    form_class = formularios.RegraDeRepasseForm
    modulo = Modulo.REPASSES
    titulo = "Editar regra de repasse"
    sucesso_url = "rede:regras"
    mensagem_de_sucesso = "Regra atualizada."

    def get_form(self, dados=None):
        regra = get_object_or_404(RegraDeRepasse, pk=self.kwargs["pk"], rede=self.request.rede)
        return self.form_class(dados or None, instance=regra, rede=self.request.rede)

    def salvar(self, dados, formulario):
        formulario.save()


class GovernancaView(PainelMixin, View):
    """Política da rede: o que a unidade não pode mudar (RF-RED-014) e a marca (RF-RED-013)."""

    modulo = Modulo.GOVERNANCA
    nivel_minimo = "admin"
    template_name = "rede/governanca.html"

    def get(self, request):
        politica_da_rede = politica(request.rede)
        return render(request, self.template_name, {
            "titulo": "Governança da rede",
            "modulo": Modulo.GOVERNANCA.value,
            "form": formularios.PoliticaDaRedeForm(instance=politica_da_rede),
            "politica": politica_da_rede,
            "travas": __import__("rede.servicos", fromlist=["travas_vigentes"]).travas_vigentes(request.rede),
            "unidades": Unidade.objects.filter(rede=request.rede),
        })

    def post(self, request):
        politica_da_rede = politica(request.rede)
        formulario = formularios.PoliticaDaRedeForm(request.POST, instance=politica_da_rede)
        if not formulario.is_valid():
            return render(request, self.template_name, {
                "titulo": "Governança da rede", "modulo": Modulo.GOVERNANCA.value,
                "form": formulario, "politica": politica_da_rede,
                "travas": __import__("rede.servicos", fromlist=["travas_vigentes"]).travas_vigentes(request.rede),
                "unidades": Unidade.objects.filter(rede=request.rede),
            })
        formulario.save()
        registrar("alterar", "politica_da_rede", entidade_id=politica_da_rede.pk,
                  descricao="Política da rede atualizada", request=request)
        messages.success(request, "Política da rede atualizada.")
        return redirect("rede:governanca")


class ComunicadosView(ListaPainel):
    model = Comunicado
    modulo = Modulo.COMUNICADOS
    titulo = "Comunicados"
    colunas = [("Quando", "criado_em"), ("Título", "titulo"), ("Público", "publico"),
               ("Unidade", "unidade"), ("Ativo", "ativo")]
    ordenacao = ("-criado_em", "-pk")
    url_novo = "rede:comunicado_criar"
    mostrar_arquivados = False

    def get_queryset(self):
        return Comunicado.objects.filter(rede=self.request.rede).select_related("unidade")

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        lidos = set(LeituraDeComunicado.objects.filter(
            usuario=self.request.user).values_list("comunicado_id", flat=True))
        contexto["lidos"] = lidos
        return contexto


class ComunicadoCriarView(FormularioDaRede):
    form_class = formularios.ComunicadoForm
    modulo = Modulo.COMUNICADOS
    titulo = "Novo comunicado"
    sucesso_url = "rede:comunicados"
    mensagem_de_sucesso = "Comunicado publicado."

    def salvar(self, dados, formulario):
        comunicado = formulario.save(commit=False)
        comunicado.rede = self.request.rede
        comunicado.criado_por = self.request.user
        comunicado.save()


class LerComunicadoView(PainelMixin, View):
    modulo = Modulo.COMUNICADOS

    def post(self, request, pk):
        comunicado = get_object_or_404(Comunicado, pk=pk, rede=request.rede)
        LeituraDeComunicado.objects.get_or_create(
            comunicado=comunicado, usuario=request.user,
            defaults={"unidade": getattr(request, "unidade", None)},
        )
        messages.success(request, "Leitura confirmada.")
        return redirect("rede:comunicados")


class AprovacoesView(ListaPainel):
    model = SolicitacaoDeAprovacao
    modulo = Modulo.APROVACOES
    titulo = "Alçadas e aprovações"
    subtitulo = "Operações sensíveis que dependem da rede (RF-RED-018)"
    colunas = [("Quando", "criado_em"), ("Tipo", "tipo"), ("Título", "titulo"),
               ("Unidade", "unidade"), ("Valor", "valor"), ("Situação", "situacao")]
    ordenacao = ("-criado_em", "-pk")
    mostrar_arquivados = False

    def get_queryset(self):
        return SolicitacaoDeAprovacao.objects.filter(rede=self.request.rede).select_related("unidade")


class DecidirAprovacaoView(PainelMixin, View):
    modulo = Modulo.APROVACOES
    nivel_minimo = "admin"

    def post(self, request, pk):
        pedido = get_object_or_404(SolicitacaoDeAprovacao, pk=pk, rede=request.rede)
        aprovar = request.POST.get("decisao") == "aprovar"
        pedido.decidir(request.user, aprovar, (request.POST.get("justificativa") or "").strip())
        registrar("decidir", "aprovacao", entidade_id=pedido.pk,
                  descricao=f"{pedido.get_tipo_display()}: {'aprovada' if aprovar else 'recusada'}",
                  request=request)
        messages.success(request, f"Solicitação {'aprovada' if aprovar else 'recusada'}.")
        return redirect("rede:aprovacoes")


class CatalogoView(PainelMixin, View):
    """Distribuição em lote do catálogo da rede para as unidades (RF-RED-006)."""

    modulo = Modulo.CATALOGO
    nivel_minimo = "editar"
    template_name = "rede/catalogo.html"

    def get(self, request):
        return render(request, self.template_name, {
            "titulo": "Catálogo da rede",
            "modulo": Modulo.CATALOGO.value,
            "form": formularios.DistribuicaoForm(rede=request.rede),
            "distribuicoes": __import__("rede.models", fromlist=["DistribuicaoDeCatalogo"])
            .DistribuicaoDeCatalogo.objects.filter(rede=request.rede)[:10],
        })

    def post(self, request):
        formulario = formularios.DistribuicaoForm(request.POST, rede=request.rede)
        if not formulario.is_valid():
            return render(request, self.template_name, {
                "titulo": "Catálogo da rede", "modulo": Modulo.CATALOGO.value, "form": formulario,
                "distribuicoes": [],
            })
        distribuicao = distribuir_catalogo(
            request.rede, formulario.cleaned_data["referencia"],
            formulario.cleaned_data["unidades"], usuario=request.user,
        )
        copias = len(distribuicao.resultado.get("copias", []))
        messages.success(request, f"Distribuído para {copias} unidade(s).")
        for erro in distribuicao.resultado.get("erros", [])[:5]:
            messages.warning(request, f"{erro}" if isinstance(erro, str) else f"{erro['unidade']}: {erro['erro']}")
        return redirect("rede:catalogo")


class TransferenciasView(PainelMixin, View):
    """Transferência de alunos entre unidades, em lote (RF-RED-004)."""

    modulo = Modulo.UNIDADES
    nivel_minimo = "editar"
    template_name = "rede/transferencias.html"

    def get(self, request):
        return render(request, self.template_name, {
            "titulo": "Transferência de alunos",
            "modulo": Modulo.UNIDADES.value,
            "form": formularios.TransferenciaForm(rede=request.rede),
            "historico": TransferenciaDeAluno.objects.filter(
                rede=request.rede).select_related("aluno", "origem", "destino")[:15],
        })

    def post(self, request):
        formulario = formularios.TransferenciaForm(request.POST, rede=request.rede)
        if not formulario.is_valid():
            return render(request, self.template_name, {
                "titulo": "Transferência de alunos", "modulo": Modulo.UNIDADES.value,
                "form": formulario, "historico": [],
            })
        origem = formulario.cleaned_data["origem"]
        destino = formulario.cleaned_data["destino"]
        from usuarios.models import Usuario

        alunos = list(Usuario.todos.filter(rede=request.rede, unidade=origem))
        if request.POST.get("confirmacao", "").strip().upper() != "TRANSFERIR":
            messages.error(request, "Para confirmar, digite TRANSFERIR no campo de confirmação.")
            return redirect("rede:transferencias")
        resultado = transferir_alunos(alunos, destino, formulario.cleaned_data.get("motivo", ""),
                                      usuario=request.user)
        messages.success(request, f"{resultado['transferidos']} aluno(s) transferido(s) "
                                  f"(lote {resultado['lote']}).")
        return redirect("rede:transferencias")


class ImportarDaRedeView(PainelMixin, View):
    """Importação multi-unidade com relatório de conferência (RF-RED-023)."""

    modulo = Modulo.UNIDADES
    nivel_minimo = "admin"
    template_name = "rede/importar.html"

    def get(self, request):
        return render(request, self.template_name, {
            "titulo": "Importar para a rede",
            "modulo": Modulo.UNIDADES.value,
            "form": formularios.ImportacaoDaRedeForm(),
            "relatorio": None,
        })

    def post(self, request):
        from gestao.importacao import analisar_aplicar_multiunidade

        formulario = formularios.ImportacaoDaRedeForm(request.POST, request.FILES)
        relatorio = None
        if formulario.is_valid():
            conteudo = formulario.cleaned_data["arquivo"].read()
            relatorio = analisar_aplicar_multiunidade(
                conteudo, request.rede, tipo=formulario.cleaned_data["tipo"],
                atualizar_existentes=formulario.cleaned_data.get("atualizar_existentes", False),
                dry_run=request.POST.get("acao") != "importar",
            )
            if request.POST.get("acao") == "importar":
                messages.success(request, relatorio["mensagem"])
            else:
                messages.info(request, "Conferência pronta — nada foi gravado ainda.")
        return render(request, self.template_name, {
            "titulo": "Importar para a rede",
            "modulo": Modulo.UNIDADES.value,
            "form": formulario,
            "relatorio": relatorio,
            "conferindo": request.POST.get("acao") != "importar",
            "arquivo_em_memoria": request.POST.get("arquivo_em_memoria", ""),
        })
