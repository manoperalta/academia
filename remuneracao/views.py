"""Telas de comissao: regras, apuracao, demonstrativo e baixa."""

from __future__ import annotations

from django.contrib import messages
from django.shortcuts import redirect
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView

from gestao.mixins import PainelMixin
from gestao.painel_base import FormularioDoPainel
from gestao.permissoes import Modulo
from gestao.views import ListaPainel
from remuneracao.forms import RegraDeComissaoForm
from remuneracao.models import ApuracaoDeComissao, RegraDeComissao
from remuneracao.servicos import apurar_competencia, marcar_paga


class RegrasView(ListaPainel):
    model = RegraDeComissao
    modulo = Modulo.COMISSOES
    titulo = "Regras de comissao"
    subtitulo = "Quanto cada professor recebe por aula, aluno ou percentual do recebido"
    colunas = (
        ("Professor", "professor"),
        ("Unidade", "unidade"),
        ("Tipo", "get_tipo_display"),
        ("Valor", "valor", "moeda"),
        ("Percentual", "percentual"),
        ("Ativa", "ativo"),
    )
    ordenacao = ("professor", "-criado_em")
    url_novo = "remuneracao:regra_nova"
    url_editar = "remuneracao:regra_editar"


class RegraNovaView(FormularioDoPainel):
    form_class = RegraDeComissaoForm
    modulo = Modulo.COMISSOES
    titulo = "Nova regra de comissao"
    sucesso_url = "remuneracao:regras"
    mensagem_de_sucesso = "Regra de comissao criada."


class RegraEditarView(FormularioDoPainel):
    form_class = RegraDeComissaoForm
    modulo = Modulo.COMISSOES
    titulo = "Editar regra de comissao"
    sucesso_url = "remuneracao:regras"
    mensagem_de_sucesso = "Regra atualizada."

    def get_objeto(self):
        return RegraDeComissao.objects.filter(pk=self.kwargs["pk"]).first()


class ApuracoesView(ListaPainel):
    model = ApuracaoDeComissao
    modulo = Modulo.COMISSOES
    titulo = "Comissoes apuradas"
    subtitulo = "Cada linha guarda a memoria de calculo do periodo"
    colunas = (
        ("Professor", "professor"),
        ("Unidade", "unidade"),
        ("Periodo", "inicio"),
        ("Devido", "valor_devido", "moeda"),
        ("Pago", "valor_pago", "moeda"),
        ("Situacao", "get_situacao_display"),
    )
    ordenacao = ("-inicio",)
    url_detalhe = "remuneracao:apuracao_detalhe"


class ApuracaoDetalheView(PainelMixin, TemplateView):
    modulo = Modulo.COMISSOES
    titulo = "Demonstrativo da comissao"
    template_name = "remuneracao/apuracao_detalhe.html"
    nivel_minimo = "ver"

    def get_context_data(self, **kwargs):
        from remuneracao.servicos import conferir_apuracao

        contexto = super().get_context_data(**kwargs)
        apuracao = ApuracaoDeComissao.objects.filter(pk=self.kwargs["pk"]).first()
        contexto["apuracao"] = apuracao
        contexto["itens"] = apuracao.itens.all() if apuracao else []
        contexto["conferencia"] = conferir_apuracao(apuracao) if apuracao else None
        return contexto


class ApurarCompetenciaView(PainelMixin, View):
    modulo = Modulo.COMISSOES
    nivel_minimo = "admin"

    def post(self, request, *args, **kwargs):
        referencia = timezone.localdate()
        resultado = apurar_competencia(
            request.rede, referencia, usuario=request.user, forcar=bool(request.POST.get("forcar"))
        )
        messages.success(
            request,
            f"{len(resultado['emitidas'])} comissao(oes) apurada(s): R$ {resultado['total']}",
        )
        for erro in resultado["erros"][:3]:
            messages.warning(request, f"{erro['professor']}: {erro['erro']}")
        return redirect("remuneracao:apuracoes")


class BaixarComissaoView(PainelMixin, View):
    modulo = Modulo.COMISSOES
    nivel_minimo = "editar"

    def post(self, request, *args, **kwargs):
        apuracao = ApuracaoDeComissao.objects.filter(pk=self.kwargs["pk"]).first()
        if apuracao is None:
            messages.error(request, "Comissao nao encontrada.")
            return redirect("remuneracao:apuracoes")
        marcar_paga(apuracao, request.POST.get("valor") or apuracao.saldo, request.user)
        messages.success(request, "Baixa registrada.")
        return redirect("remuneracao:apuracao_detalhe", pk=apuracao.pk)


class ExtratoDoProfessorView(PainelMixin, TemplateView):
    """O professor ve o proprio extrato (sem passar pela gestao da rede)."""

    modulo = Modulo.COMISSOES
    titulo = "Meu extrato de comissoes"
    template_name = "remuneracao/extrato.html"
    nivel_minimo = "ver"

    def get_context_data(self, **kwargs):
        from remuneracao.servicos import extrato_do_professor

        contexto = super().get_context_data(**kwargs)
        from professores.models import Professor

        professor = (
            Professor.todos.filter(user=self.request.user).first()
            or Professor.todos.filter(rede=self.request.rede, user__isnull=True).first()
        )
        contexto["extrato"] = extrato_do_professor(professor) if professor else None
        contexto["professor"] = professor
        return contexto
