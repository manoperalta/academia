"""Testes dos mixins de CBV: e aqui que a tela respeita rede, papel e status."""

from __future__ import annotations

import pytest
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.test import RequestFactory
from django.views.generic import ListView, View

from core.mixins import (
    EscritaPermitidaMixin,
    RedeRequiredMixin,
    UnidadeScopedMixin,
    papeis_do_usuario,
)
from core.models import Unidade, VinculoUsuario
from core.papeis import Papel, StatusRede
from tests.apoio import criar
from usuarios.models import Usuario

pytestmark = pytest.mark.django_db


class _ViewComRede(RedeRequiredMixin, View):
    papeis_permitidos = (Papel.ADMIN_REDE,)

    def get(self, request):  # pragma: no cover - so devolve ok
        return HttpResponse("ok")

    def post(self, request):  # pragma: no cover
        return HttpResponse("ok")


def _requisicao(metodo="get", *, user=None, rede=None, unidade=None):
    requisicao = getattr(RequestFactory(), metodo)("/qualquer/")
    requisicao.user = user
    requisicao.rede = rede
    requisicao.unidade = unidade
    requisicao.session = {}
    requisicao._messages = FallbackStorage(requisicao)
    return requisicao


def test_sem_rede_redireciona_para_login(usuario):
    resposta = _ViewComRede.as_view()(_requisicao(user=usuario))
    assert resposta.status_code == 302
    assert "login" in resposta["Location"]


def test_sem_vinculo_bloqueia(usuario, rede):
    with pytest.raises(PermissionDenied):
        _ViewComRede.as_view()(_requisicao(user=usuario, rede=rede))


def test_papel_errado_bloqueia(usuario, rede, unidade):
    VinculoUsuario.todos.create(usuario=usuario, rede=rede, unidade=unidade, papel=Papel.RECEPCAO)
    with pytest.raises(PermissionDenied):
        _ViewComRede.as_view()(_requisicao(user=usuario, rede=rede, unidade=unidade))


def test_papel_certo_libera(usuario, rede, unidade):
    VinculoUsuario.todos.create(usuario=usuario, rede=rede, unidade=unidade, papel=Papel.ADMIN_REDE)
    resposta = _ViewComRede.as_view()(_requisicao(user=usuario, rede=rede, unidade=unidade))
    assert resposta.status_code == 200
    assert resposta.content == b"ok"


class _ViewDeEscrita(EscritaPermitidaMixin, View):
    def post(self, request):  # pragma: no cover
        return HttpResponse("gravou")

    def get(self, request):  # pragma: no cover
        return HttpResponse("leu")


def test_escrita_bloqueada_quando_rede_esta_suspensa(usuario, rede):
    rede.status = StatusRede.SUSPENSO
    rede.save(update_fields=["status"])
    with pytest.raises(PermissionDenied):
        _ViewDeEscrita.as_view()(_requisicao("post", user=usuario, rede=rede))


def test_leitura_continua_liberada_quando_rede_esta_suspensa(usuario, rede):
    rede.status = StatusRede.SUSPENSO
    rede.save(update_fields=["status"])
    resposta = _ViewDeEscrita.as_view()(_requisicao("get", user=usuario, rede=rede))
    assert resposta.status_code == 200


class _ListaDeAluno(UnidadeScopedMixin, ListView):
    template_name = "nao-usado.html"

    def get_queryset(self):
        return super().get_queryset()


def test_recepcao_so_ve_a_propria_unidade(usuario, rede, unidade):
    """Recepcao de uma unidade nao enxerga aluno da unidade irma."""
    VinculoUsuario.todos.create(usuario=usuario, rede=rede, unidade=unidade, papel=Papel.RECEPCAO)
    irma = Unidade.todos.create(rede=rede, nome="Unidade Sul", codigo="sul")
    aluno_a = criar(Usuario, rede=rede, unidade=unidade)
    criar(Usuario, rede=rede, unidade=irma)

    class ListaDeAlunos(UnidadeScopedMixin, ListView):
        model = Usuario
        template_name = "x.html"

    view = ListaDeAlunos()
    view.request = _requisicao(user=usuario, rede=rede, unidade=unidade)
    ids = [obj.pk for obj in view.get_queryset()]
    assert ids == [aluno_a.pk]


def test_papeis_do_usuario_por_rede(rede, outra_rede, usuario):
    VinculoUsuario.todos.create(usuario=usuario, rede=rede, papel=Papel.ADMIN_REDE)
    VinculoUsuario.todos.create(usuario=usuario, rede=outra_rede, papel=Papel.PROFESSOR)
    assert papeis_do_usuario(usuario, rede) == {Papel.ADMIN_REDE}
    assert papeis_do_usuario(usuario, outra_rede) == {Papel.PROFESSOR}


def test_superusuario_e_superadmin(rede, usuario):
    usuario.is_superuser = True
    usuario.save()
    assert papeis_do_usuario(usuario, rede) == {Papel.SUPERADMIN_PLATAFORMA}
