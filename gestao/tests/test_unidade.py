"""Seletor de unidade e escopo por unidade."""
from __future__ import annotations

import pytest
from django.urls import reverse

from core.models import Unidade
from usuarios.models import Usuario


def _aluno(rede, nome, unidade):
    return Usuario.todos.create(
        rede=rede, unidade=unidade, nome=nome, email_user=f"{nome.split()[0].lower()}@exemplo.com",
        telefone_user="51000000000", status_user="Ativo",
    )


def test_trocar_unidade_grava_na_sessao(cliente_logado, unidade):
    resposta = cliente_logado.post(
        reverse("gestao:selecionar_unidade"), {"unidade": str(unidade.pk)}
    )
    assert resposta.status_code == 302
    assert cliente_logado.session["unidade_id"] == unidade.pk


def test_ver_todas_as_unidades_limpa_a_sessao(cliente_logado, unidade):
    cliente_logado.post(reverse("gestao:selecionar_unidade"), {"unidade": str(unidade.pk)})
    cliente_logado.post(reverse("gestao:selecionar_unidade"), {"unidade": ""})
    assert "unidade_id" not in cliente_logado.session


def test_sem_acesso_a_unidade_recebe_403(cliente_recepcao, unidade_da_outra_rede):
    resposta = cliente_recepcao.post(
        reverse("gestao:selecionar_unidade"), {"unidade": str(unidade_da_outra_rede.pk)}
    )
    assert resposta.status_code == 403


def test_lista_respeita_a_unidade_escolhida(cliente_logado, rede, unidade):
    filial = Unidade.todos.create(rede=rede, nome="Filial", codigo="filial")
    _aluno(rede, "Aluno Centro", unidade)
    _aluno(rede, "Aluno Filial", filial)
    cliente_logado.post(reverse("gestao:selecionar_unidade"), {"unidade": str(unidade.pk)})
    resposta = cliente_logado.get(reverse("gestao:alunos"))
    nomes = [a.nome for a in resposta.context["object_list"]]
    assert "Aluno Centro" in nomes
    assert "Aluno Filial" not in nomes


def test_sem_unidade_escolhida_ve_tudo(cliente_logado, rede, unidade):
    filial = Unidade.todos.create(rede=rede, nome="Filial", codigo="filial")
    _aluno(rede, "Aluno Centro", unidade)
    _aluno(rede, "Aluno Filial", filial)
    resposta = cliente_logado.get(reverse("gestao:alunos"))
    nomes = [a.nome for a in resposta.context["object_list"]]
    assert {"Aluno Centro", "Aluno Filial"}.issubset(set(nomes))
