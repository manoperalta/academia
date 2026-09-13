"""Diagnostico manual do isolamento na API (nao roda na suite automatica).

docker compose -f docker-compose.dev.yml run --rm web pytest tests/manual_dbg.py -s -q
"""

from __future__ import annotations

import pytest
from django.test import Client

from api.escopos import tem_escopo
from api.models import ApiToken
from api.viewsets import AlunoViewSet
from aulas.models import Aulas
from core.context import usar_rede
from tests.apoio import criar

pytestmark = pytest.mark.django_db


def test_diagnostico_listagem(rede, outra_rede):
    with usar_rede(rede):
        criar(Aulas, rede=rede)
    with usar_rede(outra_rede):
        aula_b = criar(Aulas, rede=outra_rede)

    _, credencial = ApiToken.gerar(nome="dbg", rede=rede, escopos=["aulas:read"])
    cliente = Client()
    cliente.defaults["HTTP_AUTHORIZATION"] = f"Token {credencial}"
    listagem = cliente.get("/api/v1/aulas/")
    print(f"\n[dbg] listagem={listagem.status_code} count={(listagem.json().get('count'))}")
    print(f"[dbg] detalhe de outra rede={cliente.get(f'/api/v1/aulas/{aula_b.pk}/').status_code}")
    assert listagem.json()["count"] == 1


def test_diagnostico_escopo_de_escrita(rede):
    _, credencial = ApiToken.gerar(nome="leitura", rede=rede, escopos=["alunos:read", "rede:read"])
    cliente = Client()
    cliente.defaults["HTTP_AUTHORIZATION"] = f"Token {credencial}"

    print(
        f"\n[dbg] tem_escopo(leitura, alunos:write) = {tem_escopo(['alunos:read'], 'alunos:write')}"
    )
    print(
        f"[dbg] permission_classes do AlunoViewSet = {[c.__name__ for c in AlunoViewSet.permission_classes]}"
    )

    resposta = cliente.post("/api/v1/alunos/", data={"nome": "x"}, content_type="application/json")
    print(f"[dbg] POST /api/v1/alunos/ -> {resposta.status_code}")
    print(f"[dbg] corpo={resposta.content[:500]}")
    assert resposta.status_code in {201, 400, 403}
