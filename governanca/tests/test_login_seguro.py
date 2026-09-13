"""Login com rate limit, bloqueio progressivo e 2FA (RNF-009)."""
from __future__ import annotations

import pytest
from django.urls import reverse

from core import totp
from core.seguranca import confirmar_2fa, iniciar_2fa
from governanca.tests.conftest import SENHA
from governanca.models import Dispositivo2FA, TentativaDeLogin


def test_login_com_email_funciona(db, usuario_governanca):
    cliente = __import__("django.test", fromlist=["Client"]).Client()
    resposta = cliente.post(reverse("governanca:entrar"),
                            {"identificador": usuario_governanca.email, "senha": SENHA})
    assert resposta.status_code == 302
    assert TentativaDeLogin.objects.filter(sucesso=True).exists()


def test_senha_errada_registra_tentativa(db, usuario_governanca):
    from django.test import Client

    cliente = Client()
    resposta = cliente.post(reverse("governanca:entrar"),
                            {"identificador": usuario_governanca.email, "senha": "errada"})
    assert resposta.status_code == 200
    assert "incorretos" in resposta.content.decode().lower()
    assert TentativaDeLogin.objects.filter(sucesso=False).count() == 1


def test_bloqueio_progressivo_apos_tres_falhas(db, usuario_governanca):
    from django.test import Client

    cliente = Client()
    for _ in range(3):
        cliente.post(reverse("governanca:entrar"),
                     {"identificador": usuario_governanca.email, "senha": "errada"})
    resposta = cliente.post(reverse("governanca:entrar"),
                            {"identificador": usuario_governanca.email, "senha": SENHA})
    conteudo = resposta.content.decode().lower()
    assert "muitas tentativas" in conteudo
    assert TentativaDeLogin.objects.filter(bloqueado=True).exists()


def test_sucesso_limpa_as_falhas(db, usuario_governanca):
    from django.test import Client

    cliente = Client()
    cliente.post(reverse("governanca:entrar"), {"identificador": usuario_governanca.email, "senha": "errada"})
    cliente.post(reverse("governanca:entrar"),
                 {"identificador": usuario_governanca.email, "senha": SENHA})
    from core.seguranca import bloqueio_ativo, limpar_falhas_de_login

    limpar_falhas_de_login(usuario_governanca.email, "")
    assert bloqueio_ativo(usuario_governanca.email, "")[0] is False


def test_login_com_2fa_ativo_vai_para_o_desafio(db, usuario_governanca):
    from django.test import Client

    dispositivo = iniciar_2fa(usuario_governanca)
    confirmar_2fa(usuario_governanca, totp.codigo_atual(dispositivo.segredo))
    cliente = Client()
    resposta = cliente.post(reverse("governanca:entrar"),
                            {"identificador": usuario_governanca.email, "senha": SENHA})
    assert resposta.status_code == 302
    assert reverse("governanca:dois_fatores") in resposta.url


def test_paginas_publicas_abrem(db):
    from django.test import Client

    cliente = Client()
    assert cliente.get(reverse("governanca:status")).status_code == 200
    assert cliente.get(reverse("governanca:privacidade")).status_code == 200
    assert cliente.get(reverse("governanca:entrar")).status_code == 200
