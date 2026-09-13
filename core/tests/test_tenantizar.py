"""Testes do comando de migracao de dados (tenantizar)."""

from __future__ import annotations

import pytest
from django.core.management import call_command

from aulas.models import Aulas
from core.models import Rede, Unidade
from tests.apoio import criar

pytestmark = pytest.mark.django_db


def test_tenantizar_cria_rede_padrao_e_etiqueta_dados():
    aula = criar(Aulas)
    Aulas.todos.filter(pk=aula.pk).update(rede=None)  # simula dado anterior a migracao
    assert Aulas.todos.filter(rede__isnull=True).count() == 1

    call_command("tenantizar", "--slug", "padrao", "--nome", "Academia Padrao")

    rede = Rede.todos.get(slug="padrao")
    assert rede.nome == "Academia Padrao"
    assert Unidade.todos.filter(rede=rede, codigo="matriz").exists()
    assert Aulas.todos.filter(rede__isnull=True).count() == 0
    assert Aulas.todos.get(pk=aula.pk).rede_id == rede.pk


def test_tenantizar_e_idempotente():
    criar(Aulas)
    call_command("tenantizar", "--slug", "padrao")
    call_command("tenantizar", "--slug", "padrao")
    assert Rede.todos.filter(slug="padrao").count() == 1
    assert Unidade.todos.filter(rede__slug="padrao", codigo="matriz").count() == 1
