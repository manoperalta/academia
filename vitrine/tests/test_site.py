"""Paginas publicas: home, planos, ajuda, contato e checagens ao vivo."""

from __future__ import annotations

from django.urls import reverse

from plataforma.tests.conftest import criar_pacote
from vitrine.tests.conftest import cnpj_valido


def test_home_abre_e_mostra_pacotes(client, pacotes_publicos):
    resposta = client.get(reverse("vitrine:home"))
    assert resposta.status_code == 200
    conteudo = resposta.content.decode()
    assert "Prata" in conteudo and "Bronze" in conteudo and "Ouro" in conteudo
    assert "125" in conteudo.replace("\xa0", " ")


def test_home_esconde_pacote_invisivel(client, pacotes_publicos):
    oculto = criar_pacote("interno", "Interno", 10, 1, 1, "10.00", [])
    oculto.visivel_no_site = False
    oculto.save()
    conteudo = client.get(reverse("vitrine:home")).content.decode()
    assert "Interno" not in conteudo


def test_planos_compara_modulos(client, pacotes_publicos):
    resposta = client.get(reverse("vitrine:planos"))
    assert resposta.status_code == 200
    conteudo = resposta.content.decode()
    assert "Relatórios avançados" in conteudo or "Relatorios avancados" in conteudo
    assert "WhatsApp" in conteudo


def test_ajuda_lista_topicos(client, db):
    resposta = client.get(reverse("vitrine:ajuda"))
    assert resposta.status_code == 200
    assert "Central de ajuda" in resposta.content.decode()


def test_cadastro_sugere_slug_e_pacote(client, pacotes_publicos):
    resposta = client.get(reverse("vitrine:cadastro"), {"plano": "ouro"})
    assert resposta.status_code == 200
    assert resposta.context["pacote_escolhido"].codigo == "ouro"


def test_verificacao_de_slug_ao_vivo(client, db, rede):
    livre = client.get(reverse("vitrine:verificar_slug"), {"slug": "academia-nova"})
    assert livre.json() == {"disponivel": True, "mensagem": ""}
    ocupado = client.get(reverse("vitrine:verificar_slug"), {"slug": rede.slug})
    assert ocupado.json()["disponivel"] is False
    reservado = client.get(reverse("vitrine:verificar_slug"), {"slug": "admin"})
    assert reservado.json()["disponivel"] is False


def test_verificacao_de_cnpj_ao_vivo(client, db):
    valido = client.get(reverse("vitrine:verificar_cnpj"), {"cnpj": cnpj_valido()})
    assert valido.json()["valido"] is True
    invalido = client.get(reverse("vitrine:verificar_cnpj"), {"cnpj": "11.111.111/1111-11"})
    assert invalido.json()["valido"] is False


def test_contato_envia_email(client, db):
    resposta = client.post(
        reverse("vitrine:contato"),
        {
            "nome": "Fulano",
            "email": "fulano@exemplo.com",
            "telefone": "51",
            "academia": "Academia X",
            "mensagem": "Quero uma demonstracao",
        },
    )
    assert resposta.status_code == 200
    assert resposta.context["enviado"] is True
