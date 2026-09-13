"""Downloads dos documentos de negocio em PDF.

Todo documento passa por tres crivos: usuario logado (o mixin do painel), modulo permitido
(o mesmo da tela equivalente) e **escopo da rede** — objeto de outra rede nao existe para
quem esta logado em uma, entao a resposta e 404, nunca um PDF de outro cliente.
"""

from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, HttpResponse
from django.views import View

from area_do_aluno.views import aluno_da_sessao
from documentos import servicos
from financeiro.models import Pagamento
from gestao.mixins import PainelMixin
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
