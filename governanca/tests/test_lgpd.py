"""LGPD: exportacao, anonimizacao, pedidos e acesso a dado sensivel (RNF-006)."""
from __future__ import annotations

import io
import json
import zipfile
from datetime import timedelta

import pytest
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from api.models import RegistroAuditoria
from financeiro.models import Pagamento
from governanca.models import (
    AcessoDadoSensivel,
    RegraRetencao,
    SolicitacaoTitular,
    TentativaDeLogin,
)
from governanca.servicos import (
    anonimizar_titular, aplicar_retencao, dados_do_titular, exportar_titular_zip, prazo_do_pedido,
)
from usuarios.models import Usuario


def test_dados_do_titular_inclui_cadastro_ficha_e_pagamentos(db, rede, aluno_com_login):
    dados = dados_do_titular(rede, aluno_com_login["aluno"])
    assert dados["cadastro"]["nome"] == "Ana Aluna"
    assert dados["cadastro"]["cpf"] == "111.444.777-35"
    assert dados["ficha_saude"]["restricoes"] == "joelho"
    assert len(dados["pagamentos"]) == 1


def test_zip_de_exportacao_do_titular(db, rede, aluno_com_login):
    conteudo = exportar_titular_zip(rede, aluno_com_login["aluno"])
    pacote = zipfile.ZipFile(io.BytesIO(conteudo))
    nomes = pacote.namelist()
    assert "dados.json" in nomes and "leia-me.txt" in nomes
    dados = json.loads(pacote.read("dados.json"))
    assert dados["cadastro"]["nome"] == "Ana Aluna"
    assert dados["ficha_saude"]["obs"] == "faz musculacao"


def test_exportacao_pelo_painel_e_auditada(cliente_governanca, rede, aluno_com_login):
    resposta = cliente_governanca.get(
        reverse("gestao:privacidade_exportar", args=[aluno_com_login["aluno"].pk]))
    assert resposta.status_code == 200
    assert resposta["Content-Type"] == "application/zip"
    assert RegistroAuditoria.objects.filter(acao="exportar", entidade="titular").exists()


def test_anonimizacao_preserva_pagamento_e_limpa_dados(db, rede, aluno_com_login):
    aluno = aluno_com_login["aluno"]
    resultado = anonimizar_titular(rede, aluno, motivo="pedido do titular")
    aluno.refresh_from_db()
    assert aluno.nome == resultado["marcador"] and aluno.nome.startswith("ANONIMIZADO-")
    assert "anonimizado.local" in aluno.email_user
    assert aluno.cpf_cnpj_user == "" and aluno.telefone_user == ""
    assert aluno.status_user == "Inativo"
    # pagamento permanece (obrigacao fiscal)
    assert Pagamento.objects.filter(pk=aluno_com_login["pagamento"].pk).exists()
    assert RegistroAuditoria.objects.filter(acao="anonimizar", entidade="titular").exists()


def test_anonimizacao_pelo_painel_exige_confirmacao(cliente_governanca, rede, aluno_com_login):
    aluno = aluno_com_login["aluno"]
    resposta = cliente_governanca.post(
        reverse("gestao:privacidade_anonimizar", args=[aluno.pk]), {"confirmacao": "sim"})
    assert resposta.status_code == 302
    aluno.refresh_from_db()
    assert aluno.nome == "Ana Aluna"  # nada mudou
    certo = cliente_governanca.post(
        reverse("gestao:privacidade_anonimizar", args=[aluno.pk]), {"confirmacao": "ANONIMIZAR"})
    assert certo.status_code == 302
    aluno.refresh_from_db()
    assert aluno.nome.startswith("ANONIMIZADO-")


def test_pedido_de_titular_tem_prazo_de_15_dias(cliente_governanca, rede):
    resposta = cliente_governanca.post(reverse("gestao:privacidade_solicitar"), {
        "titular_nome": "Ana Aluna", "titular_email": "ana@exemplo.com", "tipo": "eliminacao",
        "descricao": "Quero meus dados removidos",
    })
    assert resposta.status_code == 302
    pedido = SolicitacaoTitular.objects.get(rede=rede)
    assert pedido.prazo_em == prazo_do_pedido()
    assert pedido.atrasada is False
    assert RegistroAuditoria.objects.filter(entidade="solicitacao_titular").exists()


def test_pedido_atrasado_e_sinalizado(db, rede):
    pedido = SolicitacaoTitular.objects.create(
        rede=rede, titular_nome="Ana", tipo="acesso",
        prazo_em=timezone.localdate() - timedelta(days=1),
    )
    assert pedido.atrasada is True


def test_leitura_da_ficha_de_saude_e_registrada(cliente_governanca, rede, aluno_com_login):
    AcessoDadoSensivel.objects.all().delete()
    resposta = cliente_governanca.get(reverse("gestao:aluno_detalhe", args=[aluno_com_login["aluno"].pk]))
    assert resposta.status_code == 200
    acesso = AcessoDadoSensivel.objects.get(rede=rede)
    assert acesso.titular_nome == "Ana Aluna"
    assert acesso.recurso == "ficha_saude" and acesso.acao == "leitura"


def test_retencao_conta_vencidos_e_respeita_base_legal(db, rede):
    call_command("seed_governanca")
    antigo = TentativaDeLogin.objects.create(identificador="alguem@exemplo.com", sucesso=False)
    TentativaDeLogin.objects.filter(pk=antigo.pk).update(
        criado_em=timezone.now() - timedelta(days=400))
    resultado = aplicar_retencao(dry_run=True)
    entidades = {regra["entidade"]: regra for regra in resultado["regras"]}
    assert "tentativas_login" in entidades
    assert entidades["tentativas_login"]["registros"] == 1
    assert entidades["tentativas_login"]["acao"] == "Eliminar"
    assert TentativaDeLogin.objects.filter(pk=antigo.pk).exists()  # dry-run nao apaga

    aplicar_retencao(dry_run=False)
    assert not TentativaDeLogin.objects.filter(pk=antigo.pk).exists()


def test_politica_de_privacidade_publica(client, db):
    call_command("seed_governanca")
    resposta = client.get(reverse("governanca:privacidade"))
    assert resposta.status_code == 200
    conteudo = resposta.content.decode()
    assert "operadora" in conteudo and "controladora" in conteudo
    assert "pagamento" in conteudo.lower()


def test_regras_de_retencao_do_seed(db):
    call_command("seed_governanca")
    assert RegraRetencao.objects.filter(ativo=True).count() == 6
    assert RegraRetencao.objects.get(entidade="pagamento").acao == "conservar"
