"""Telas de integracoes: a lista de provedores e os campos de cada um.

O fluxo e o pedido pelo produto: escolher a integracao e, ao escolher, aparecerem os campos
com os valores que o terceiro fornece (chave da API, token, usuario, certificado...).
"""

from __future__ import annotations

from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import TemplateView

from api.auditoria import registrar
from gestao.mixins import EdicaoMixin, PainelMixin
from gestao.permissoes import Modulo
from integracoes import catalogo, servicos
from integracoes.forms import EscolherProvedorForm, formulario_do_provedor


class IntegracoesView(PainelMixin, TemplateView):
    """Lista os provedores e o estado de cada um nesta rede."""

    template_name = "integracoes/lista.html"
    modulo = Modulo.INTEGRACOES
    titulo = "Integracoes"
    subtitulo = "Provedores de terceiros e os valores que eles fornecem"

    def get(self, request, *args, **kwargs):
        escolhido = (request.GET.get("provedor") or "").strip().lower()
        if escolhido:
            return redirect("integracoes:configurar", provedor=escolhido)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["escolher"] = EscolherProvedorForm()
        panorama = {item["chave"]: item for item in servicos.panorama(self.request.rede)}
        grupos = []
        for categoria, integracoes in catalogo.por_categoria().items():
            linhas = []
            for integracao in integracoes:
                item = dict(panorama[integracao.chave])
                if item["ativa"]:
                    item["estado"], item["classe"] = "ativa", "bg-emerald-100 text-emerald-800"
                elif item["configurada"]:
                    item["estado"], item["classe"] = "preenchida", "bg-amber-100 text-amber-800"
                else:
                    item["estado"], item["classe"] = "sem valores", "bg-slate-100 text-slate-600"
                linhas.append(item)
            grupos.append({"categoria": categoria, "itens": linhas})
        contexto["grupos"] = grupos
        return contexto


class ConfigurarIntegracaoView(EdicaoMixin, View):
    """Formulario do provedor escolhido, montado a partir do catalogo."""

    template_name = "integracoes/formulario.html"
    modulo = Modulo.INTEGRACOES
    titulo = "Configurar integracao"

    def _contexto(self, request, integracao, formulario):
        return {
            "integracao": integracao,
            "form": formulario,
            "escolher": EscolherProvedorForm(initial={"provedor": integracao.chave}),
            "titulo": f"{integracao.nome}",
            "subtitulo": integracao.resumo,
            "situacao_atual": integracao.situacao_atual,
            "aviso": integracao.aviso,
            "docs": integracao.docs,
            "espelho": integracao.espelho,
            "pode_editar": True,
            "url_voltar": reverse("integracoes:painel"),
        }

    def get(self, request, provedor=""):
        chave = (provedor or request.GET.get("provedor") or "").strip().lower()
        integracao = catalogo.obter(chave)
        if integracao is None:
            messages.info(request, "Escolha uma integracao para ver os campos que ela pede.")
            return redirect("integracoes:painel")
        formulario = formulario_do_provedor(
            chave, valores=servicos.valores_reais(request.rede, chave)
        )
        if request.GET.get("gerar_token") == "1" and "token" in formulario.fields:
            formulario.fields["token"].initial = servicos.token_sugerido()
        return render(request, self.template_name, self._contexto(request, integracao, formulario))

    def post(self, request, provedor=""):
        chave = (provedor or request.POST.get("provedor") or "").strip().lower()
        integracao = catalogo.obter(chave)
        if integracao is None:
            messages.error(request, "Integracao desconhecida.")
            return redirect("integracoes:painel")
        formulario = formulario_do_provedor(
            chave,
            valores=servicos.valores_reais(request.rede, chave),
            data=request.POST,
            files=request.FILES,
        )
        if not formulario.is_valid():
            messages.error(request, "Confira os campos destacados.")
            return render(
                request, self.template_name, self._contexto(request, integracao, formulario)
            )
        registro = servicos.salvar(
            request.rede, chave, dict(formulario.cleaned_data), usuario=request.user
        )
        registrar(
            "alterar",
            "integracao",
            entidade_id=registro.pk,
            descricao=f"Integracao {integracao.nome} atualizada via painel",
            request=request,
        )
        messages.success(request, f"{integracao.nome}: valores salvos.")
        return redirect("integracoes:configurar", provedor=chave)


class TestarIntegracaoView(EdicaoMixin, View):
    """Diz o que ja da para afirmar sobre a integracao (sem inventar conexao)."""

    modulo = Modulo.INTEGRACOES

    def post(self, request, provedor=""):
        chave = (provedor or request.POST.get("provedor") or "").strip().lower()
        if catalogo.obter(chave) is None:
            messages.error(request, "Integracao desconhecida.")
            return redirect("integracoes:painel")
        pronto, recado = servicos.testar(request.rede, chave)
        registrar(
            "consultar",
            "integracao",
            descricao=f"Teste da integracao {chave}: {recado}",
            request=request,
        )
        (messages.success if pronto else messages.warning)(request, recado)
        return redirect("integracoes:configurar", provedor=chave)
