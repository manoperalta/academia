"""A biblioteca de aulas e da rede: o material de um professor serve aos colegas.

Ate 14/09/2026 a tela listava so as aulas do proprio professor ("Minhas Aulas"), embora a
composicao de treinos ja oferecesse as da rede -- o professor nao reaproveitava nada.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from aulas.models import Aulas
from professores.models import Professor


def _aula(rede, unidade, autor, nome):
    return Aulas.todos.create(
        rede=rede,
        unidade=unidade,
        nome=nome,
        descricao="Descricao de teste",
        professor=autor,
        categorias_exercicios="forca",
    )


@pytest.fixture
def colega(rede, unidade):
    pessoa = get_user_model().objects.create_user(
        username="colega@exemplo.com", password="senha-de-teste-123", is_professor=True
    )
    Professor.todos.create(rede=rede, unidade=unidade, nome="Colega de Rede", user=pessoa)
    return pessoa


@pytest.fixture
def aulas_da_rede(db, rede, unidade, usuario, colega):
    return {
        "minha": _aula(rede, unidade, usuario, "Aula do dono"),
        "colega": _aula(rede, unidade, colega, "Aula do colega"),
    }


def test_lista_traz_as_aulas_de_todos_os_professores(cliente_logado, aulas_da_rede):
    html = cliente_logado.get(reverse("aulas_list")).content.decode()
    assert "Aula do dono" in html
    assert "Aula do colega" in html
    assert "Aulas da academia" in html


def test_aula_de_colega_nao_oferece_edicao(cliente_logado, aulas_da_rede):
    html = cliente_logado.get(reverse("aulas_list")).content.decode()
    assert "aula de outro professor da rede" in html
    # o proprio material continua editavel
    assert reverse("aulas_update", args=[aulas_da_rede["minha"].pk]) in html
    assert reverse("aulas_update", args=[aulas_da_rede["colega"].pk]) not in html


def test_filtro_meus_preserva_o_recorte_antigo(cliente_logado, aulas_da_rede):
    html = cliente_logado.get(reverse("aulas_list") + "?meus=1").content.decode()
    assert "Aula do dono" in html
    assert "Aula do colega" not in html
    assert "Mostrando apenas as suas aulas" in html


def test_biblioteca_e_isolada_por_rede(cliente_logado, outra_rede, unidade_da_outra_rede, usuario):
    _aula(outra_rede, unidade_da_outra_rede, usuario, "Aula de outra rede")
    html = cliente_logado.get(reverse("aulas_list")).content.decode()
    assert "Aula de outra rede" not in html


def test_aula_arquivada_sai_da_biblioteca(cliente_logado, aulas_da_rede):
    from django.utils import timezone

    aula = aulas_da_rede["colega"]
    aula.arquivado_em = timezone.now()
    aula.save(update_fields=["arquivado_em"])
    html = cliente_logado.get(reverse("aulas_list")).content.decode()
    assert "Aula do colega" not in html
