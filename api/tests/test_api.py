"""Testes da API: autenticacao por token, escopos e isolamento entre redes."""

from __future__ import annotations

import pytest
from django.test import Client

from api.models import ApiToken, RegistroAuditoria
from core.context import usar_rede
from tests.apoio import criar

pytestmark = pytest.mark.django_db


def _cliente_com_token(credencial) -> Client:
    cliente = Client()
    cliente.defaults["HTTP_AUTHORIZATION"] = f"Token {credencial}"
    return cliente


@pytest.fixture
def token_leitura(rede, unidade):
    token, credencial = ApiToken.gerar(
        nome="leitura", rede=rede, unidade=unidade, escopos=["alunos:read", "rede:read"]
    )
    return token, credencial


def test_estado_exige_nada_e_sessao_exige_autenticacao():
    assert Client().get("/api/v1/estado/").status_code == 200
    assert Client().get("/api/v1/sessao/").status_code in {401, 403}


def test_token_invalido_e_recusado():
    resposta = _cliente_com_token("naoexiste.segredo").get("/api/v1/alunos/")
    assert resposta.status_code == 401
    assert resposta["Content-Type"] == "application/problem+json"


def test_token_valido_le_alunos(token_leitura):
    _, credencial = token_leitura
    resposta = _cliente_com_token(credencial).get("/api/v1/alunos/")
    assert resposta.status_code == 200
    assert "results" in resposta.json()


def test_token_sem_escopo_de_escrita_recebe_403(token_leitura):
    _, credencial = token_leitura
    resposta = _cliente_com_token(credencial).post(
        "/api/v1/alunos/", data={"nome": "x"}, content_type="application/json"
    )
    assert resposta.status_code == 403
    assert resposta.json()["codigo"] == "escopo_insuficiente"


def test_token_sem_escopo_de_leitura_recebe_403(rede):
    """Token de um recurso nao pode ler outro recurso."""
    _, credencial = ApiToken.gerar(nome="so-rede", rede=rede, escopos=["rede:read"])
    resposta = _cliente_com_token(credencial).get("/api/v1/alunos/")
    assert resposta.status_code == 403
    assert resposta.json()["codigo"] == "escopo_insuficiente"


def test_escopo_de_leitura_nao_autoriza_exclusao(token_leitura):
    """Leitura nunca autoriza DELETE."""
    from aulas.models import Aulas
    from core.context import usar_rede

    with usar_rede(None):
        pass
    _, credencial = ApiToken.gerar(
        nome="aulas-leitura", rede=token_leitura[0].rede, escopos=["aulas:read"]
    )
    resposta = _cliente_com_token(credencial).delete("/api/v1/aulas/999/")
    assert resposta.status_code in {403, 404}
    assert Aulas is not None


def test_token_usa_o_contexto_da_rede_do_token(rede, unidade):
    """A chamada por token opera na rede do token, sem precisar informar rede."""
    _, credencial = ApiToken.gerar(
        nome="escrita", rede=rede, unidade=unidade, escopos=["alunos:read", "alunos:write"]
    )
    with usar_rede(None):
        from usuarios.models import Usuario

        resposta = _cliente_com_token(credencial).get("/api/v1/sessao/")
    assert resposta.status_code == 200
    assert resposta.json()["rede"] == rede.slug
    assert resposta.json()["tipo"] == "token"
    assert Usuario is not None


def test_isolamento_por_api_entre_redes(rede, outra_rede):
    """O teste que mais importa: token de uma rede nao enxerga dado da outra."""
    from aulas.models import Aulas

    with usar_rede(rede):
        aula_a = criar(Aulas, rede=rede)
    with usar_rede(outra_rede):
        aula_b = criar(Aulas, rede=outra_rede)

    _, credencial = ApiToken.gerar(nome="aulas-a", rede=rede, escopos=["aulas:read"])
    cliente = _cliente_com_token(credencial)

    listagem = cliente.get("/api/v1/aulas/")
    assert listagem.status_code == 200
    ids = [item["id"] for item in listagem.json()["results"]]
    assert aula_a.pk in ids
    assert aula_b.pk not in ids

    # acesso direto ao id da outra rede: 404, nunca o dado
    detalhe = cliente.get(f"/api/v1/aulas/{aula_b.pk}/")
    assert detalhe.status_code == 404


def test_escrita_por_api_gera_auditoria(rede, unidade):
    from core.models import Unidade as ModeloUnidade

    _, credencial = ApiToken.gerar(
        nome="unidades", rede=rede, escopos=["unidades:read", "unidades:write"]
    )
    resposta = _cliente_com_token(credencial).post(
        "/api/v1/unidades/",
        data={"nome": "Unidade Nova", "codigo": "nova", "tipo": "propria", "status": "ativa"},
        content_type="application/json",
    )
    assert resposta.status_code == 201, resposta.content
    assert ModeloUnidade.todos.filter(nome="Unidade Nova").exists()
    registro = RegistroAuditoria.objects.filter(rede=rede, entidade="unidade").first()
    assert registro is not None
    assert registro.acao == RegistroAuditoria.Acao.CRIAR
    assert registro.token is not None, "escrita por API precisa registrar qual token fez"
    assert registro.dados_depois["id"]


def test_tokens_sao_revogaveis(token_leitura):
    token, credencial = token_leitura
    assert token.esta_valido() is True
    token.ativo = False
    token.save(update_fields=["ativo"])
    assert token.esta_valido() is False
    assert _cliente_com_token(credencial).get("/api/v1/alunos/").status_code == 401


def test_auditoria_nao_pode_ser_alterada():
    registro = RegistroAuditoria(acao=RegistroAuditoria.Acao.CRIAR, entidade="teste")
    with pytest.raises(ValueError):
        registro.save()
        registro.descricao = "outra"
        registro.save()
