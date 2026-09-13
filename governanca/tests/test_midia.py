"""Media isolada por cliente com sessao obrigatoria (RNF-010)."""
from __future__ import annotations

from governanca.tests.conftest import SENHA
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse


def test_anonimo_e_enviado_para_o_login(client, rede, arquivo_de_midia):
    resposta = client.get(reverse("governanca:midia", args=[f"redes/{rede.slug}/logo.png"]))
    assert resposta.status_code == 302
    assert reverse("governanca:entrar") in resposta.url


def test_dono_recebe_o_arquivo(cliente_governanca, rede, arquivo_de_midia):
    resposta = cliente_governanca.get(reverse("governanca:midia", args=[f"redes/{rede.slug}/logo.png"]))
    assert resposta.status_code == 200
    assert b"PNG" in b"".join(resposta.streaming_content)


def test_usuario_de_outra_academia_recebe_404(db, rede, arquivo_de_midia):
    usuario = get_user_model().objects.create_user(username="intruso", password=SENHA)
    cliente = Client()
    cliente.force_login(usuario)
    resposta = cliente.get(reverse("governanca:midia", args=[f"redes/{rede.slug}/logo.png"]))
    assert resposta.status_code == 404


def test_caminho_com_volta_de_pasta_e_recusado(cliente_governanca, rede, arquivo_de_midia):
    resposta = cliente_governanca.get(
        reverse("governanca:midia", args=[f"redes/{rede.slug}/../../../etc/passwd"])
    )
    assert resposta.status_code == 404


def test_caminho_e_do_tenant_ignora_dono_errado(db, rede, outra_rede):
    from core.seguranca import caminho_e_do_tenant

    assert caminho_e_do_tenant(f"redes/{rede.slug}/a.png", rede) is True
    assert caminho_e_do_tenant(f"redes/{rede.slug}/a.png", outra_rede) is False
    assert caminho_e_do_tenant("logos/a.png", rede) is False
    assert caminho_e_do_tenant("redes/../a.png", rede) is False
