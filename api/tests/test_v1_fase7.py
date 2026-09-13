"""API v1 da fase 7: JWT, escopos, paginacao, ETag, idempotencia, lote, webhooks e jobs."""

from __future__ import annotations

import pytest
from django.urls import reverse
from django.utils import timezone

from api import jwt as jwt_api
from api.models import (
    ApiToken,
    EntregaDeWebhook,
    RegistroAuditoria,
    TarefaAssincrona,
    WebhookDeSaida,
)


@pytest.fixture
def token(db, rede):
    return ApiToken.gerar(
        rede=rede,
        nome="token de teste",
        escopos=[
            "alunos:read",
            "alunos:write",
            "rede:read",
            "rede:write",
            "repasses:read",
            "repasses:write",
            "financeiro:read",
            "financeiro:write",
            "unidades:read",
            "unidades:write",
            "equipe:read",
            "professores:read",
            "aulas:read",
            "agenda:read",
            "comunicacao:read",
            "comunicacao:write",
            "relatorios:read",
            "auditoria:read",
            "webhooks:write",
            "saude:read",
        ],
    )


@pytest.fixture
def autorizacao(token):
    _objeto, segredo = token
    return {"HTTP_AUTHORIZATION": f"Token {segredo}"}


# ------------------------------------------------------------------ JWT
def test_jwt_emite_e_valida():
    token = jwt_api.emitir("42", escopos=["alunos:read"])
    dados = jwt_api.validar(token, tipo="acesso")
    assert dados["sub"] == "42" and dados["escopos"] == ["alunos:read"]


def test_jwt_recusa_assinatura_errada_e_expirado():
    token = jwt_api.emitir("42", validade=-10)
    with pytest.raises(jwt_api.TokenInvalido):
        jwt_api.validar(token)
    valido = jwt_api.emitir("42")
    cabecalho, corpo, _ = valido.split(".")
    with pytest.raises(jwt_api.TokenInvalido):
        jwt_api.validar(f"{cabecalho}.{corpo}.assinatura-falsa")


def test_entrar_com_senha_devolve_jwt(client, db, rede, admin_da_rede_senha):
    usuario, senha = admin_da_rede_senha
    resposta = client.post(
        "/api/v1/auth/token/",
        {"email": usuario.email, "senha": senha},
        content_type="application/json",
    )
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["acesso"] and corpo["renovacao"] and corpo["expira_em"] == 3600
    renovado = client.post(
        "/api/v1/auth/refresh/", {"renovacao": corpo["renovacao"]}, content_type="application/json"
    )
    assert renovado.status_code == 200 and renovado.json()["acesso"]


def test_entrar_com_senha_errada_responde_rfc7807(client, db, rede, admin_da_rede_senha):
    usuario, _senha = admin_da_rede_senha
    resposta = client.post(
        "/api/v1/auth/token/",
        {"email": usuario.email, "senha": "errada"},
        content_type="application/json",
    )
    assert resposta.status_code == 401
    corpo = resposta.json()
    assert corpo["status"] == 401 and corpo["codigo"] == "credenciais_invalidas"
    assert "title" in corpo and "detail" in corpo


# ------------------------------------------------------------------ escopo e isolamento
def test_sem_escopo_de_leitura_recebe_403(client, db, rede, receita):
    _restrito, segredo = ApiToken.gerar(rede=rede, nome="so alunos", escopos=["alunos:read"])
    resposta = client.get("/api/v1/planos/", HTTP_AUTHORIZATION=f"Token {segredo}")
    assert resposta.status_code == 403


def test_token_sem_escopo_de_escrita_nao_cria(client, db, rede):
    _restrito, segredo = ApiToken.gerar(rede=rede, nome="token restrito", escopos=["alunos:read"])
    resposta = client.post(
        "/api/v1/planos/",
        {"nome": "Plano X", "valor": "100.00", "tipo": "mensal"},
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Token {segredo}",
    )
    assert resposta.status_code == 403
    assert resposta.json()["codigo"] == "escopo_insuficiente"


def test_recorte_por_rede_do_token(client, db, rede, outras_redes, token, autorizacao):
    resposta = client.get("/api/v1/alunos/", **autorizacao)
    assert resposta.status_code == 200
    nomes = {item["nome"] for item in resposta.json()["results"]}
    assert all(not nome.startswith("Outra") for nome in nomes)


# ------------------------------------------------------------------ paginacao, filtros, ETag
def test_lista_com_paginacao_filtro_e_ordenacao(client, db, rede, token, autorizacao, receita):
    resposta = client.get("/api/v1/alunos/?page=1&ordering=-nome&status_user=Ativo", **autorizacao)
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert "results" in corpo and corpo["count"] > 0
    nomes = [item["nome"] for item in corpo["results"]]
    assert nomes == sorted(nomes, reverse=True)


def test_busca_incremental_updated_since(client, db, rede, token, autorizacao, receita):
    agora = timezone.now().isoformat()
    vazio = client.get(f"/api/v1/alunos/?updated_since={agora}", **autorizacao)
    assert vazio.status_code == 200
    assert vazio.json()["count"] == 0


def test_etag_devolve_304(client, db, rede, token, autorizacao, receita):
    primeira = client.get("/api/v1/alunos/", **autorizacao)
    etiqueta = primeira.headers.get("ETag")
    assert etiqueta
    segunda = client.get("/api/v1/alunos/", HTTP_IF_NONE_MATCH=etiqueta, **autorizacao)
    assert segunda.status_code == 304


# ------------------------------------------------------------------ idempotencia, dry_run, lote
def test_idempotency_key_nao_duplica(client, db, rede, token, autorizacao):
    corpo = {"nome": "Plano Idempotente", "valor": "120.00", "tipo": "mensal"}
    primeira = client.post(
        "/api/v1/planos/",
        corpo,
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="chave-1",
        **autorizacao,
    )
    segunda = client.post(
        "/api/v1/planos/",
        corpo,
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="chave-1",
        **autorizacao,
    )
    assert primeira.status_code == 201 and segunda.status_code == 201
    assert segunda.headers.get("Idempotency-Replayed") == "true"
    assert primeira.json()["id"] == segunda.json()["id"]


def test_dry_run_nao_grava(client, db, rede, token, autorizacao):
    from financeiro.models import Plano

    antes = Plano.objects.count()
    resposta = client.post(
        "/api/v1/planos/?dry_run=1",
        {"nome": "Simulado", "valor": "99.00", "tipo": "mensal"},
        content_type="application/json",
        **autorizacao,
    )
    assert resposta.status_code == 200 and resposta.json()["dry_run"] is True
    assert Plano.objects.count() == antes


def test_lote_com_relatorio_por_item_e_desfazer(client, db, rede, token, autorizacao):
    from financeiro.models import Plano

    itens = [
        {"nome": "Plano A", "valor": "100.00", "tipo": "mensal"},
        {"nome": "Plano B", "valor": "200.00", "tipo": "mensal"},
        {"nome": "", "valor": "0"},
    ]
    previa = client.post(
        "/api/v1/planos/lote/?dry_run=1", itens, content_type="application/json", **autorizacao
    )
    assert previa.json()["dry_run"] is True and previa.json()["criados"] == 2
    assert Plano.objects.count() == 0

    criado = client.post(
        "/api/v1/planos/lote/", itens, content_type="application/json", **autorizacao
    )
    corpo = criado.json()
    assert corpo["criados"] == 2 and corpo["erros"] and len(corpo["criados_ids"]) == 2

    desfeito = client.post(
        "/api/v1/planos/desfazer/",
        {"ids": corpo["criados_ids"]},
        content_type="application/json",
        **autorizacao,
    )
    assert desfeito.json()["revertidos"] == 2


# ------------------------------------------------------------------ webhooks
def test_webhook_entrega_assinada_e_retentativa(db, rede, monkeypatch):
    from api import webhooks

    webhook = WebhookDeSaida.objects.create(
        rede=rede,
        url="https://exemplo.com/hook",
        eventos=["repasse.emitido"],
        segredo=WebhookDeSaida.gerar_segredo(),
    )
    entregas = webhooks.disparar_evento("repasse.emitido", {"repasse": 1}, rede=rede)
    assert len(entregas) == 1
    entrega = entregas[0]

    capturado = {}

    def postar_ok(url, corpo, cabecalhos, timeout=10):
        capturado.update({"url": url, "corpo": corpo, "cabecalhos": cabecalhos})
        return 200, "ok"

    monkeypatch.setattr(webhooks, "_postar", postar_ok)
    entrega = webhooks.entregar(entrega)
    assert entrega.situacao == EntregaDeWebhook.Situacao.ENTREGUE
    assert capturado["cabecalhos"]["X-Assinatura"].startswith("sha256=")
    esperado = webhook.assina(capturado["corpo"], int(capturado["cabecalhos"]["X-Timestamp"]))
    assert capturado["cabecalhos"]["X-Assinatura"] == f"sha256={esperado}"
    assert capturado["cabecalhos"]["X-Evento"] == "repasse.emitido"

    def postar_falha(url, corpo, cabecalhos, timeout=10):
        raise OSError("connection refused")

    monkeypatch.setattr(webhooks, "_postar", postar_falha)
    nova = webhooks.disparar_evento("repasse.emitido", {"repasse": 2}, rede=rede)[0]
    nova = webhooks.entregar(nova)
    assert nova.situacao == EntregaDeWebhook.Situacao.FALHOU
    assert nova.tentativas == 1 and nova.proxima_tentativa is not None  # backoff agendado
    reenviada = webhooks.reenviar(nova)
    assert reenviada.tentativas == 1 and reenviada.situacao != EntregaDeWebhook.Situacao.ENTREGUE


def test_webhook_nao_escuta_evento_fora_da_lista(db, rede):
    from api import webhooks

    WebhookDeSaida.objects.create(
        rede=rede, url="https://exemplo.com/hook", eventos=["aluno.criado"], segredo="x"
    )
    assert webhooks.disparar_evento("repasse.emitido", {}, rede=rede) == []
    with pytest.raises(ValueError):
        webhooks.disparar_evento("evento.inventado", {}, rede=rede)


# ------------------------------------------------------------------ jobs e relatorios
def test_relatorio_vira_job_e_gera_csv(client, db, rede, token, autorizacao, receita):
    from api.tarefas import processar_pendentes

    resposta = client.post(
        "/api/v1/relatorios/rede/", {}, content_type="application/json", **autorizacao
    )
    assert resposta.status_code == 202
    tarefa_id = resposta.json()["tarefa"]
    acompanhamento = client.get(f"/api/v1/jobs/{tarefa_id}/", **autorizacao)
    assert acompanhamento.json()["situacao"] == TarefaAssincrona.Situacao.NA_FILA

    processar_pendentes()
    concluido = client.get(f"/api/v1/jobs/{tarefa_id}/", **autorizacao).json()
    assert concluido["situacao"] == TarefaAssincrona.Situacao.CONCLUIDA
    baixado = client.get(f"/api/v1/tarefas/{tarefa_id}/download/", **autorizacao)
    assert baixado.status_code == 200
    conteudo = baixado.content.decode()
    assert "Unidade" in conteudo and "Total recebido" in conteudo


def test_estado_do_tenant_responde_com_limites_e_filas(client, db, rede, token, autorizacao):
    resposta = client.get("/api/v1/estado-da-rede/", **autorizacao)
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["versao"] == "v1"
    assert "rotinas" in corpo and "integracao" in corpo
    assert corpo.get("rede", {}).get("nome") == rede.nome


# ------------------------------------------------------------------ auditoria por token
def test_escrita_pela_api_fica_auditada_com_o_token(client, db, rede, token, autorizacao):
    objeto, _segredo = token
    resposta = client.post(
        "/api/v1/planos/",
        {"nome": "Plano Auditado", "valor": "150.00", "tipo": "mensal"},
        content_type="application/json",
        **autorizacao,
    )
    assert resposta.status_code == 201
    registro = RegistroAuditoria.objects.filter(entidade="plano").first()
    assert registro is not None
    assert registro.token_id == objeto.pk


# ------------------------------------------------------------------ paridade tela x endpoint
def test_paridade_entre_telas_e_endpoints():
    """Cada tela de escrita do painel tem endpoint equivalente (RF-API-010)."""
    mapa = {
        "rede:unidades": "/api/v1/unidades/",
        "rede:repasses": "/api/v1/repasses/",
        "rede:metas": "/api/v1/metas/",
        "rede:comunicados": "/api/v1/comunicados/",
        "gestao:alunos": "/api/v1/alunos/",
        "gestao:professores": "/api/v1/professores/",
        "gestao:planos": "/api/v1/planos/",
        "gestao:pagamentos": "/api/v1/pagamentos/",
    }
    for rota, endpoint in mapa.items():
        assert reverse(rota), f"tela {rota} sem rota"
        assert endpoint.startswith("/api/v1/"), endpoint


def test_catalogo_tem_os_30_recursos():
    from api.recursos import RECURSOS

    assert len(RECURSOS) == 30
    escopos = {recurso.escopo for recurso in RECURSOS}
    assert {
        "plataforma",
        "unidades",
        "alunos",
        "financeiro",
        "repasses",
        "rede",
        "auditoria",
    } <= escopos
