"""Downloads dos documentos de negocio em PDF.

Todo documento passa por tres crivos: usuario logado (o mixin do painel), modulo permitido
(o mesmo da tela equivalente) e **escopo da rede** — objeto de outra rede nao existe para
quem esta logado em uma, entao a resposta e 404, nunca um PDF de outro cliente.
"""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import DetailView, ListView

from area_do_aluno.views import aluno_da_sessao
from documentos import assinatura, servicos
from documentos.assinatura import ErroDeAssinatura
from documentos.models import EnvelopeDeAssinatura, Signatario
from financeiro.models import Pagamento
from gestao.mixins import EdicaoMixin, PainelMixin
from gestao.permissoes import Modulo
from rede.models import Repasse
from remuneracao.models import ApuracaoDeComissao
from usuarios.models import Usuario


class DocumentoDaRedeView(PainelMixin, View):
    """Base dos documentos do painel: busca no escopo da rede e devolve o PDF."""

    modulo = Modulo.ALUNOS
    nome_do_documento = "documento"

    def buscar(self, pk: str):
        raise NotImplementedError

    def gerar(self, objeto) -> bytes:
        raise NotImplementedError

    def get(self, request, pk: str, *args, **kwargs):
        objeto = self.buscar(pk)
        if objeto is None:
            raise Http404("documento-nao-encontrado")
        conteudo = self.gerar(objeto)
        resposta = HttpResponse(conteudo, content_type="application/pdf")
        resposta["Content-Disposition"] = f'inline; filename="{self.nome_do_documento}-{pk}.pdf"'
        resposta["X-Documento"] = self.nome_do_documento
        return resposta


class ComprovanteDeMatriculaView(DocumentoDaRedeView):
    modulo = Modulo.ALUNOS
    nome_do_documento = "comprovante-de-matricula"

    def buscar(self, pk):
        return Usuario.todos.filter(pk=pk, rede=self.request.rede).select_related("user").first()

    def gerar(self, objeto):
        return servicos.comprovante_de_matricula(objeto.user)


class CarteirinhaDoAlunoView(DocumentoDaRedeView):
    modulo = Modulo.ALUNOS
    nome_do_documento = "carteirinha"

    def buscar(self, pk):
        return Usuario.todos.filter(pk=pk, rede=self.request.rede).select_related("user").first()

    def gerar(self, objeto):
        return servicos.carteirinha_do_aluno(objeto.user)


class ContratoDeAdesaoView(DocumentoDaRedeView):
    modulo = Modulo.ALUNOS
    nome_do_documento = "contrato-de-adesao"

    def buscar(self, pk):
        return Usuario.todos.filter(pk=pk, rede=self.request.rede).select_related("user").first()

    def gerar(self, objeto):
        return servicos.contrato_de_adesao(objeto.user)


class ReciboDePagamentoView(DocumentoDaRedeView):
    modulo = Modulo.FINANCEIRO
    nome_do_documento = "recibo-de-pagamento"

    def buscar(self, pk):
        return Pagamento.objects.filter(pk=pk, rede=self.request.rede).first()

    def gerar(self, objeto):
        return servicos.recibo_de_pagamento(objeto)


class DemonstrativoDeRepasseView(DocumentoDaRedeView):
    modulo = Modulo.REPASSES
    nome_do_documento = "demonstrativo-de-repasse"

    def buscar(self, pk):
        return Repasse.objects.filter(pk=pk, rede=self.request.rede).first()

    def gerar(self, objeto):
        return servicos.demonstrativo_de_repasse(objeto)


class ExtratoDeComissaoView(DocumentoDaRedeView):
    modulo = Modulo.COMISSOES
    nome_do_documento = "extrato-de-comissao"

    def buscar(self, pk):
        return ApuracaoDeComissao.objects.filter(pk=pk, rede=self.request.rede).first()

    def gerar(self, objeto):
        return servicos.extrato_de_comissao(objeto)


class MinhaCarteirinhaView(LoginRequiredMixin, View):
    """O proprio aluno baixa a carteirinha dele no PWA."""

    def get(self, request, *args, **kwargs):
        aluno = aluno_da_sessao(request)
        if aluno is None:
            raise Http404("sem-perfil-de-aluno")
        conteudo = servicos.carteirinha_do_aluno(aluno.user)
        resposta = HttpResponse(conteudo, content_type="application/pdf")
        resposta["Content-Disposition"] = 'inline; filename="minha-carteirinha.pdf"'
        return resposta


# ------------------------------------------------------------------ assinatura eletronica
class EnvelopesView(PainelMixin, ListView):
    """Documentos a colher assinatura e em que pe estao."""

    modulo = Modulo.ALUNOS
    template_name = "documentos/envelopes.html"
    context_object_name = "envelopes"
    paginate_by = 25

    def get_queryset(self):
        return EnvelopeDeAssinatura.objects.filter(rede=self.request.rede).select_related("aluno")

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["resumo"] = assinatura.resumo_das_assinaturas(self.request.rede)
        contexto["alunos"] = Usuario.todos.filter(rede=self.request.rede)[:200]
        contexto["tipos"] = EnvelopeDeAssinatura.Tipo.choices
        return contexto


class CriarEnvelopeView(EdicaoMixin, View):
    modulo = Modulo.ALUNOS

    def post(self, request, *args, **kwargs):
        aluno = Usuario.todos.filter(pk=request.POST.get("aluno"), rede=request.rede).first()
        if aluno is None:
            messages.error(request, "Escolha o aluno do documento.")
            return redirect("documentos:envelopes")
        try:
            envelope = assinatura.criar_envelope(
                rede=request.rede,
                aluno=aluno,
                titulo=request.POST.get("titulo", ""),
                tipo=request.POST.get("tipo") or EnvelopeDeAssinatura.Tipo.CONTRATO,
                criado_por=request.user,
            )
        except ErroDeAssinatura as erro:
            messages.error(request, str(erro))
            return redirect("documentos:envelopes")
        messages.success(request, "Documento enviado para assinatura.")
        return redirect("documentos:envelope", pk=envelope.pk)


class EnvelopeDetalheView(PainelMixin, DetailView):
    modulo = Modulo.ALUNOS
    template_name = "documentos/envelope.html"
    context_object_name = "envelope"

    def get_queryset(self):
        return EnvelopeDeAssinatura.objects.filter(rede=self.request.rede).select_related("aluno")

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["signatarios"] = self.object.signatarios.order_by("ordem", "pk")
        contexto["proximo"] = assinatura.proximo_signatario(self.object)
        contexto["conferencia"] = assinatura.verificar(self.object)
        return contexto


def _signatario_do_painel(request, pk):
    return get_object_or_404(Signatario.objects.filter(envelope__rede=request.rede), pk=pk)


class AssinarEnvelopeView(EdicaoMixin, View):
    modulo = Modulo.ALUNOS

    def post(self, request, pk: int, *args, **kwargs):
        signatario = _signatario_do_painel(request, pk)
        try:
            assinatura.assinar(
                signatario=signatario,
                ip=_ip_do_pedido(request),
                navegador=request.META.get("HTTP_USER_AGENT", ""),
            )
        except ErroDeAssinatura as erro:
            messages.error(request, str(erro))
        else:
            messages.success(request, f"{signatario.nome} assinou.")
        return redirect("documentos:envelope", pk=signatario.envelope_id)


class RecusarEnvelopeView(EdicaoMixin, View):
    modulo = Modulo.ALUNOS

    def post(self, request, pk: int, *args, **kwargs):
        signatario = _signatario_do_painel(request, pk)
        try:
            assinatura.recusar(signatario=signatario, motivo=request.POST.get("motivo", ""))
        except ErroDeAssinatura as erro:
            messages.error(request, str(erro))
        else:
            messages.success(request, "Recusa registrada.")
        return redirect("documentos:envelope", pk=signatario.envelope_id)


class TermoDeAssinaturasView(PainelMixin, View):
    modulo = Modulo.ALUNOS

    def get(self, request, pk: int, *args, **kwargs):
        envelope = get_object_or_404(EnvelopeDeAssinatura.objects.filter(rede=request.rede), pk=pk)
        conteudo = assinatura.termo_de_assinaturas(envelope)
        resposta = HttpResponse(conteudo, content_type="application/pdf")
        resposta["Content-Disposition"] = f'inline; filename="termo-de-assinaturas-{pk}.pdf"'
        return resposta


class VerificarEnvelopeView(PainelMixin, View):
    modulo = Modulo.ALUNOS

    def post(self, request, pk: int, *args, **kwargs):
        envelope = get_object_or_404(EnvelopeDeAssinatura.objects.filter(rede=request.rede), pk=pk)
        conferencia = assinatura.verificar(envelope)
        if conferencia["ok"]:
            messages.success(
                request,
                f"Corrente integral: {conferencia['assinaturas']} assinatura(s) conferida(s).",
            )
        else:
            messages.error(
                request, "Divergencia encontrada: " + " | ".join(conferencia["divergencias"])
            )
        return redirect("documentos:envelope", pk=pk)


def _ip_do_pedido(request) -> str:
    encaminhado = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if encaminhado:
        return encaminhado.split(",")[0].strip()[:45]
    return (request.META.get("REMOTE_ADDR", "") or "")[:45]
