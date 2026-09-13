"""Telas do PDV: balcao, produtos e estoque."""

from __future__ import annotations

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import DetailView, ListView, TemplateView

from gestao.mixins import EdicaoMixin, PainelMixin
from gestao.permissoes import Modulo
from pdv import servicos
from pdv.models import ItemDaVenda, MovimentoDeEstoque, Produto, Venda
from pdv.servicos import ErroDePdv
from usuarios.models import Usuario


def _produtos(request):
    return Produto.objects.filter(rede=request.rede)


def _vendas(request):
    return Venda.objects.filter(rede=request.rede).select_related("aluno", "unidade")


class PainelDoPdvView(PainelMixin, TemplateView):
    modulo = Modulo.PDV
    template_name = "pdv/painel.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["resumo"] = servicos.resumo_do_pdv(self.request.rede)
        contexto["alertas"] = servicos.produtos_abaixo_do_minimo(self.request.rede)
        contexto["ultimas"] = _vendas(self.request)[:10]
        return contexto


class ProdutosView(PainelMixin, ListView):
    modulo = Modulo.PDV
    template_name = "pdv/produtos.html"
    context_object_name = "produtos"
    paginate_by = 50

    def get_queryset(self):
        return _produtos(self.request).order_by("nome")

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["unidades"] = self.request.rede.unidades.all()
        return contexto


class SalvarProdutoView(EdicaoMixin, View):
    modulo = Modulo.PDV

    def post(self, request, *args, **kwargs):
        unidade = request.rede.unidades.filter(pk=request.POST.get("unidade")).first()
        try:
            servicos.cadastrar_produto(
                rede=request.rede,
                unidade=unidade,
                nome=request.POST.get("nome", ""),
                preco_de_venda=request.POST.get("preco_de_venda") or 0,
                custo=request.POST.get("custo") or 0,
                codigo=request.POST.get("codigo", ""),
                estoque_inicial=int(request.POST.get("estoque_inicial") or 0),
                estoque_minimo=int(request.POST.get("estoque_minimo") or 0),
            )
        except ErroDePdv as erro:
            messages.error(request, str(erro))
        except ValueError:
            messages.error(request, "Quantidade de estoque invalida.")
        else:
            messages.success(request, "Produto salvo.")
        return redirect("pdv:produtos")


class MovimentarEstoqueView(EdicaoMixin, View):
    modulo = Modulo.PDV

    def post(self, request, pk: int, *args, **kwargs):
        produto = get_object_or_404(_produtos(request), pk=pk)
        try:
            if request.POST.get("novo_saldo"):
                servicos.ajustar_estoque(
                    produto=produto,
                    novo_saldo=int(request.POST["novo_saldo"]),
                    motivo=request.POST.get("motivo", ""),
                    criado_por=request.user,
                )
            else:
                servicos.registrar_entrada(
                    produto=produto,
                    quantidade=int(request.POST.get("quantidade") or 0),
                    motivo=request.POST.get("motivo", ""),
                    criado_por=request.user,
                )
        except ErroDePdv as erro:
            messages.error(request, str(erro))
        except ValueError:
            messages.error(request, "Quantidade invalida.")
        else:
            messages.success(request, f"Estoque de {produto.nome} atualizado.")
        return redirect("pdv:produtos")


class BalcaoView(PainelMixin, TemplateView):
    """A venda aberta do operador, com os itens ja lancados."""

    modulo = Modulo.PDV
    template_name = "pdv/balcao.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        venda = servicos.abrir_venda(
            rede=self.request.rede,
            unidade=getattr(self.request.user, "unidade", None),
            criada_por=self.request.user,
        )
        contexto["venda"] = venda
        contexto["itens"] = venda.itens.select_related("produto")
        contexto["produtos"] = _produtos(self.request).filter(ativo=True).order_by("nome")
        contexto["formas"] = Venda.FormaDePagamento.choices
        contexto["alunos"] = Usuario.todos.filter(rede=self.request.rede)[:200]
        return contexto


class AdicionarItemView(EdicaoMixin, View):
    modulo = Modulo.PDV

    def post(self, request, *args, **kwargs):
        venda = get_object_or_404(
            _vendas(request), pk=request.POST.get("venda"), situacao=Venda.Situacao.ABERTA
        )
        produto = get_object_or_404(_produtos(request), pk=request.POST.get("produto"))
        try:
            servicos.adicionar_item(
                venda=venda, produto=produto, quantidade=int(request.POST.get("quantidade") or 1)
            )
        except ErroDePdv as erro:
            messages.error(request, str(erro))
        except ValueError:
            messages.error(request, "Quantidade invalida.")
        return redirect("pdv:balcao")


class RemoverItemView(EdicaoMixin, View):
    modulo = Modulo.PDV

    def post(self, request, pk: int, *args, **kwargs):
        item = get_object_or_404(
            ItemDaVenda.objects.filter(venda__rede=request.rede, venda__situacao="aberta"), pk=pk
        )
        try:
            servicos.remover_item(venda=item.venda, item=item)
        except ErroDePdv as erro:
            messages.error(request, str(erro))
        return redirect("pdv:balcao")


class DescontoView(EdicaoMixin, View):
    modulo = Modulo.PDV

    def post(self, request, pk: int, *args, **kwargs):
        venda = get_object_or_404(_vendas(request), pk=pk, situacao=Venda.Situacao.ABERTA)
        try:
            servicos.aplicar_desconto(venda=venda, desconto=request.POST.get("desconto") or 0)
        except ErroDePdv as erro:
            messages.error(request, str(erro))
        return redirect("pdv:balcao")


class FinalizarVendaView(EdicaoMixin, View):
    modulo = Modulo.PDV

    def post(self, request, pk: int, *args, **kwargs):
        venda = get_object_or_404(_vendas(request), pk=pk)
        try:
            servicos.finalizar_venda(
                venda=venda,
                forma_de_pagamento=request.POST.get("forma_de_pagamento"),
                criado_por=request.user,
            )
        except ErroDePdv as erro:
            messages.error(request, str(erro))
            return redirect("pdv:balcao")
        messages.success(request, f"Venda finalizada: R$ {venda.total}.")
        return redirect("pdv:venda", pk=venda.pk)


class VendasView(PainelMixin, ListView):
    modulo = Modulo.PDV
    template_name = "pdv/vendas.html"
    context_object_name = "vendas"
    paginate_by = 50

    def get_queryset(self):
        consulta = _vendas(self.request)
        situacao = self.request.GET.get("situacao", "").strip()
        if situacao:
            consulta = consulta.filter(situacao=situacao)
        return consulta

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["situacoes"] = Venda.Situacao.choices
        contexto["filtro"] = self.request.GET.get("situacao", "")
        return contexto


class VendaDetalheView(PainelMixin, DetailView):
    modulo = Modulo.PDV
    template_name = "pdv/venda.html"
    context_object_name = "venda"

    def get_queryset(self):
        return _vendas(self.request)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["itens"] = self.object.itens.select_related("produto")
        contexto["movimentos"] = self.object.movimentos.select_related("produto")
        return contexto


class CancelarVendaView(EdicaoMixin, View):
    modulo = Modulo.PDV

    def post(self, request, pk: int, *args, **kwargs):
        venda = get_object_or_404(_vendas(request), pk=pk)
        try:
            servicos.cancelar_venda(
                venda=venda, motivo=request.POST.get("motivo", ""), criado_por=request.user
            )
        except ErroDePdv as erro:
            messages.error(request, str(erro))
        else:
            messages.success(request, "Venda cancelada e estoque devolvido.")
        return redirect("pdv:venda", pk=venda.pk)


class MovimentosView(PainelMixin, ListView):
    modulo = Modulo.PDV
    template_name = "pdv/movimentos.html"
    context_object_name = "movimentos"
    paginate_by = 100

    def get_queryset(self):
        return MovimentoDeEstoque.objects.filter(produto__rede=self.request.rede).select_related(
            "produto", "venda"
        )
