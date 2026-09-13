"""Testes da busca global."""

from __future__ import annotations

import pytest
from django.urls import reverse

from busca import servicos

pytestmark = pytest.mark.django_db


def nomes_dos_grupos(resultado) -> set[str]:
    return {grupo["nome"] for grupo in resultado["grupos"]}


def test_busca_acha_em_varias_fontes_de_uma_vez(rede, admin_do_painel, cenario_buscavel):
    resultado = servicos.buscar(rede, "maria", usuario=admin_do_painel)
    grupos = nomes_dos_grupos(resultado)
    assert "Alunos" in grupos
    assert "Leads" in grupos
    assert "Midia" in grupos
    assert "Pagamentos" in grupos
    assert resultado["total"] >= 4
    assert all(item.url for grupo in resultado["grupos"] for item in grupo["resultados"]), (
        "todo resultado aponta para uma tela"
    )


def test_busca_por_login_e_por_email_do_aluno(rede, admin_do_painel, cenario_buscavel):
    por_login = servicos.buscar(rede, "maria.buscavel", usuario=admin_do_painel)
    assert "Alunos" in nomes_dos_grupos(por_login)
    por_email = servicos.buscar(rede, "maria@exemplo", usuario=admin_do_painel)
    assert "Alunos" in nomes_dos_grupos(por_email)


def test_busca_nao_atravessa_a_rede(rede, outra_rede, admin_do_painel, cenario_buscavel):
    from django.contrib.auth import get_user_model

    from core.models import Unidade
    from usuarios.models import Usuario

    unidade_alheia = Unidade.objects.create(rede=outra_rede, nome="Filial Alheia", codigo="alheia")
    login = get_user_model().objects.create_user(username="maria.alheia", password="SenhaAlheia!23")
    Usuario.todos.create(
        rede=outra_rede,
        unidade=unidade_alheia,
        user=login,
        nome="Maria Alheia",
        status_user="Ativo",
    )
    resultado = servicos.buscar(rede, "maria", usuario=admin_do_painel)
    titulos = [item.titulo for grupo in resultado["grupos"] for item in grupo["resultados"]]
    assert "Maria Alheia" not in titulos


def test_papel_sem_financeiro_nao_acha_pagamento(rede, professor_do_painel, cenario_buscavel):
    resultado = servicos.buscar(rede, "maria", usuario=professor_do_painel)
    grupos = nomes_dos_grupos(resultado)
    assert "Pagamentos" not in grupos, "professor nao alcanca o modulo financeiro"
    assert "Pagamentos" in resultado["fontes_puladas"]


def test_termo_curto_nao_busca(rede, admin_do_painel, cenario_buscavel):
    resultado = servicos.buscar(rede, "m", usuario=admin_do_painel)
    assert resultado["curto"] is True
    assert resultado["total"] == 0


def test_termo_sem_resultado(rede, admin_do_painel, cenario_buscavel):
    resultado = servicos.buscar(rede, "zzzznaoexiste", usuario=admin_do_painel)
    assert resultado["total"] == 0 and resultado["curto"] is False


def test_limite_por_grupo_e_respeitado(rede, admin_do_painel, cenario_buscavel):
    from relacionamento import servicos as servicos_de_crm

    for posicao in range(8):
        servicos_de_crm.registrar_lead(rede=rede, nome=f"Maria {posicao}", telefone="")
    resultado = servicos.buscar(rede, "maria", usuario=admin_do_painel, limite_por_grupo=3)
    for grupo in resultado["grupos"]:
        assert len(grupo["resultados"]) <= 3


def test_tela_da_busca_mostra_os_grupos(cliente_painel, cenario_buscavel):
    resposta = cliente_painel.get(reverse("busca:resultados"), {"q": "maria"})
    assert resposta.status_code == 200
    corpo = resposta.content.decode()
    assert "maria" in corpo.lower()
    for grupo in ("Alunos", "Leads", "Midia", "Pagamentos"):
        assert grupo in corpo


def test_tela_sem_termo_pede_dois_caracteres(cliente_painel, cenario_buscavel):
    resposta = cliente_painel.get(reverse("busca:resultados"))
    assert resposta.status_code == 200
    assert "pelo menos 2 caracteres" in resposta.content.decode()


def test_visitante_nao_busca(client):
    assert client.get(reverse("busca:resultados"), {"q": "maria"}).status_code in (302, 403)
