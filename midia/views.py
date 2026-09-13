"""Telas e API do envio em partes, do player e da entrega assinada.

O envio e feito em partes justamente para aguentar arquivo grande em conexao ruim: a tela manda
uma parte de cada vez, mostra o progresso e **reenvia apenas a parte que falhou**. A entrega do
arquivo nunca usa caminho cru: sai sempre por URL assinada e temporaria.
"""

from __future__ import annotations

import json
import mimetypes

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_protect
from django.views.generic import DetailView, ListView, TemplateView

from aulas.models import Aulas
from gestao.mixins import EdicaoMixin, PainelMixin
from gestao.permissoes import Modulo
from midia import servicos
from midia.models import ArquivoDeMidia
from midia.servicos import ErroDeMidia


def _da_rede(request):
    return ArquivoDeMidia.objects.filter(rede=request.rede)


class ListaDeMidiaView(PainelMixin, ListView):
    """Arquivos da rede, com filtro por situacao e tipo."""

    modulo = Modulo.AULAS
    template_name = "midia/lista.html"
    context_object_name = "arquivos"
    paginate_by = 20

    def get_queryset(self):
        consulta = _da_rede(self.request).exclude(situacao=ArquivoDeMidia.Situacao.REMOVIDO)
        situacao = self.request.GET.get("situacao", "").strip()
        tipo = self.request.GET.get("tipo", "").strip()
        if situacao:
            consulta = consulta.filter(situacao=situacao)
        if tipo:
            consulta = consulta.filter(tipo=tipo)
        return consulta.select_related("unidade", "aula")

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["resumo"] = servicos.estatisticas(self.request.rede)
        contexto["situacoes"] = ArquivoDeMidia.Situacao.choices
        contexto["tipos"] = ArquivoDeMidia.Tipo.choices
        contexto["filtro_situacao"] = self.request.GET.get("situacao", "")
        contexto["filtro_tipo"] = self.request.GET.get("tipo", "")
        return contexto


class EnvioDeMidiaView(EdicaoMixin, TemplateView):
    """Tela de envio em partes."""

    modulo = Modulo.AULAS
    template_name = "midia/envio.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["tipos"] = ArquivoDeMidia.Tipo.choices
        contexto["tamanho_da_parte"] = servicos.TAMANHO_DA_PARTE
        contexto["aulas"] = Aulas.todos.filter(rede=self.request.rede).order_by("nome")[:200]
        return contexto


class IniciarEnvioView(EdicaoMixin, View):
    """Abre o envio e responde como fatiar o arquivo."""

    modulo = Modulo.AULAS

    def post(self, request, *args, **kwargs):
        try:
            dados = json.loads(request.body or b"{}")
        except json.JSONDecodeError:
            return JsonResponse({"erro": "Pedido invalido."}, status=400)
        aula = None
        if dados.get("aula"):
            aula = Aulas.todos.filter(pk=dados["aula"], rede=request.rede).first()
        try:
            arquivo = servicos.iniciar_envio(
                rede=request.rede,
                titulo=dados.get("titulo", ""),
                nome_original=dados.get("nome", ""),
                tamanho=int(dados.get("tamanho") or 0),
                tipo=dados.get("tipo", "video"),
                criado_por=request.user,
                unidade=getattr(request.user, "unidade", None),
                aula=aula,
                hash_esperado=dados.get("hash", ""),
                mime=dados.get("mime", ""),
            )
        except ErroDeMidia as erro:
            return JsonResponse({"erro": str(erro)}, status=400)
        except (TypeError, ValueError):
            return JsonResponse({"erro": "Tamanho do arquivo invalido."}, status=400)
        return JsonResponse(
            {
                "id": arquivo.pk,
                "tamanho_da_parte": servicos.TAMANHO_DA_PARTE,
                "total_de_partes": arquivo.total_de_partes,
                "url_parte": f"/midia/api/{arquivo.pk}/parte/",
                "url_concluir": f"/midia/api/{arquivo.pk}/concluir/",
                "url_status": f"/midia/api/{arquivo.pk}/status/",
            }
        )


@method_decorator(csrf_protect, name="dispatch")
class ReceberParteView(EdicaoMixin, View):
    """Recebe uma parte (multipart) e confere o hash dela."""

    modulo = Modulo.AULAS

    def post(self, request, pk: int, *args, **kwargs):
        arquivo = get_object_or_404(_da_rede(request), pk=pk)
        parte = request.FILES.get("parte")
        if parte is None:
            return JsonResponse({"erro": "Nenhuma parte foi enviada."}, status=400)
        try:
            numero = int(request.POST.get("numero") or 0)
        except ValueError:
            return JsonResponse({"erro": "Numero de parte invalido."}, status=400)
        try:
            gravada = servicos.receber_parte(
                arquivo=arquivo,
                numero=numero,
                conteudo=parte.read(),
                hash_esperado=request.POST.get("hash", ""),
            )
        except ErroDeMidia as erro:
            return JsonResponse({"erro": str(erro)}, status=400)
        return JsonResponse(
            {
                "parte": gravada.numero,
                "tamanho": gravada.tamanho_bytes,
                "recebidas": arquivo.partes_recebidas,
                "total_de_partes": arquivo.total_de_partes,
                "progresso": arquivo.progresso,
            }
        )


class ConcluirEnvioView(EdicaoMixin, View):
    """Junta as partes, confere o hash final e processa o arquivo."""

    modulo = Modulo.AULAS

    def post(self, request, pk: int, *args, **kwargs):
        arquivo = get_object_or_404(_da_rede(request), pk=pk)
        try:
            arquivo = servicos.concluir_envio(arquivo)
        except ErroDeMidia as erro:
            return JsonResponse({"erro": str(erro)}, status=400)
        return JsonResponse(
            {
                "id": arquivo.pk,
                "situacao": arquivo.situacao,
                "progresso": arquivo.progresso,
                "tamanho": arquivo.tamanho_bytes,
                "hash": arquivo.hash_final,
                "url_player": f"/midia/arquivo/{arquivo.pk}/",
            }
        )


class StatusDoEnvioView(PainelMixin, View):
    """Consulta usada pela tela enquanto o envio acontece."""

    modulo = Modulo.AULAS

    def get(self, request, pk: int, *args, **kwargs):
        arquivo = get_object_or_404(_da_rede(request), pk=pk)
        return JsonResponse(
            {
                "situacao": arquivo.situacao,
                "progresso": arquivo.progresso,
                "recebidas": arquivo.partes_recebidas,
                "total_de_partes": arquivo.total_de_partes,
                "erro": arquivo.erro,
            }
        )


class PlayerDaMidiaView(PainelMixin, DetailView):
    """Player do painel, com link assinado gerado na hora."""

    modulo = Modulo.AULAS
    template_name = "midia/player.html"
    context_object_name = "arquivo"

    def get_queryset(self):
        return _da_rede(self.request).select_related("aula", "unidade")

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        arquivo = self.object
        contexto["url_do_arquivo"] = arquivo.url_de_entrega(minutos=30)
        contexto["expira_em_minutos"] = 30
        return contexto


class EntregaDaMidiaView(View):
    """Entrega o arquivo para quem tem a URL assinada (temporaria), sem expor o caminho."""

    def get(self, request, pk: int, *args, **kwargs):
        token = request.GET.get("t", "")
        try:
            minutos = int(request.GET.get("min") or 15)
        except ValueError:
            minutos = 15
        try:
            arquivo = servicos.arquivo_do_token(token, minutos=minutos)
        except ErroDeMidia as erro:
            return JsonResponse({"erro": str(erro)}, status=403)
        if arquivo.pk != int(pk):
            return JsonResponse({"erro": "Link nao corresponde ao arquivo."}, status=403)
        caminho = servicos.caminho_absoluto(arquivo)
        if not caminho.is_file():
            raise Http404("Arquivo nao encontrado no armazenamento.")
        interno = f"{settings.MEDIA_URL.rstrip('/')}/{arquivo.caminho}"
        if getattr(settings, "USAR_X_ACCEL", False):
            resposta = HttpResponseRedirect("")
            resposta["X-Accel-Redirect"] = interno
            return resposta
        tipo = arquivo.mime or mimetypes.guess_type(caminho.name)[0] or "application/octet-stream"
        return FileResponse(caminho.open("rb"), content_type=tipo)


class MidiaDoAlunoView(View):
    """O aluno assiste a aula publicada da propria rede, tambem por link assinado."""

    def get(self, request, pk: int, *args, **kwargs):
        from area_do_aluno.views import aluno_da_sessao

        aluno = aluno_da_sessao(request)
        if aluno is None:
            raise Http404("sem-perfil-de-aluno")
        arquivo = ArquivoDeMidia.objects.filter(
            pk=pk, rede=aluno.rede, publicado=True, situacao=ArquivoDeMidia.Situacao.PRONTO
        ).first()
        if arquivo is None:
            raise Http404("Midia nao encontrada.")
        return HttpResponseRedirect(arquivo.url_de_entrega(minutos=30))
