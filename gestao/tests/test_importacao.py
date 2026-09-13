"""Importacao CSV de alunos e professores (RF-PLT-034)."""

from __future__ import annotations

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from api.models import RegistroAuditoria
from gestao.importacao import analisar
from plataforma.models import Assinatura, Pacote
from plataforma.tests.conftest import criar_alunos
from professores.models import Professor
from usuarios.models import Usuario

CABECALHO = "nome;email;telefone;cpf;nascimento;status\n"
ALUNOS_OK = (
    CABECALHO
    + "Ana Lima;ana@exemplo.com;51999990001;111.444.777-35;10/05/1990;Ativo\n"
    + "Bruno Sa;bruno@exemplo.com;51999990002;;22/03/1995;Ativo\n"
    + "Carla Dias;carla@exemplo.com;51999990003;;;Inativo\n"
)
ALUNOS_COM_PROBLEMAS = (
    CABECALHO
    + "Ana Lima;ana@exemplo.com;51;;;Ativo\n"
    + ";sem-nome@exemplo.com;51;;;Ativo\n"
    + "Email Ruim;isso-nao-e-email;51;;;Ativo\n"
    + "Repetido;ana@exemplo.com;51;;;Ativo\n"
)


@pytest.fixture
def pacote(db):
    return Pacote.objects.create(
        nome="Prata", codigo="prata", limite_alunos=3, limite_professores=1, preco_mensal="125.00"
    )


@pytest.fixture
def assinatura_do_tenant(db, rede, pacote):
    from django.utils import timezone

    return Assinatura.objects.create(
        rede=rede,
        pacote=pacote,
        ciclo="mensal",
        inicio=timezone.localdate(),
        renovacao_em=timezone.localdate(),
    )


def _upload(conteudo: str):
    return SimpleUploadedFile("alunos.csv", conteudo.encode("utf-8"), content_type="text/csv")


def test_modelo_de_planilha_disponivel(cliente_logado):
    resposta = cliente_logado.get(reverse("gestao:importar_modelo"))
    assert resposta.status_code == 200
    assert resposta.content.decode("utf-8").startswith("\ufeff")
    assert "nome;" in resposta.content.decode("utf-8")


def test_previa_conta_linhas_e_aponta_erros(cliente_logado, rede):
    resposta = cliente_logado.post(
        reverse("gestao:importar"),
        {"acao": "analisar", "tipo": "alunos", "arquivo": _upload(ALUNOS_COM_PROBLEMAS)},
    )
    assert resposta.status_code == 200
    resultado = resposta.context["resultado"]
    assert resultado.total == 4
    assert len(resultado.a_criar) == 1
    assert len(resultado.com_erro) == 3
    motivos = " ".join(" ".join(linha.motivos) for linha in resultado.com_erro)
    assert "sem nome" in motivos
    assert "e-mail invalido" in motivos
    assert "duplicado no proprio arquivo" in motivos
    assert Usuario.todos.filter(rede=rede).count() == 0  # previa nao grava


def test_confirmacao_grava_os_alunos(cliente_logado, rede):
    cliente_logado.post(
        reverse("gestao:importar"),
        {"acao": "analisar", "tipo": "alunos", "arquivo": _upload(ALUNOS_OK)},
    )
    resposta = cliente_logado.post(
        reverse("gestao:importar"), {"acao": "confirmar", "tipo": "alunos"}
    )
    assert resposta.status_code == 302
    alunos = Usuario.todos.filter(rede=rede)
    assert alunos.count() == 3
    ana = alunos.get(email_user="ana@exemplo.com")
    assert ana.status_user == "Ativo"
    assert ana.data_nasc is not None
    assert RegistroAuditoria.objects.filter(acao="importar", entidade="alunos").exists()


def test_importacao_respeita_o_teto_do_pacote(cliente_logado, rede, assinatura_do_tenant):
    criar_alunos(rede, 2)  # limite do pacote de teste = 3
    resposta = cliente_logado.post(
        reverse("gestao:importar"),
        {"acao": "analisar", "tipo": "alunos", "arquivo": _upload(ALUNOS_OK)},
    )
    resultado = resposta.context["resultado"]
    assert len(resultado.a_criar) == 1
    assert len(resultado.com_erro) == 2
    assert "limite do pacote" in resultado.com_erro[0].motivos[0]
    cliente_logado.post(reverse("gestao:importar"), {"acao": "confirmar", "tipo": "alunos"})
    assert Usuario.todos.filter(rede=rede).count() == 3  # nunca passa do teto


def test_duplicado_da_base_e_ignorado(cliente_logado, rede):
    Usuario.todos.create(
        rede=rede, nome="Ana Antiga", email_user="ana@exemplo.com", status_user="Ativo"
    )
    resposta = cliente_logado.post(
        reverse("gestao:importar"),
        {"acao": "analisar", "tipo": "alunos", "arquivo": _upload(ALUNOS_OK)},
    )
    resultado = resposta.context["resultado"]
    assert len(resultado.ignoradas) == 1
    assert len(resultado.a_criar) == 2


def test_atualizar_quando_pedido(cliente_logado, rede):
    Usuario.todos.create(
        rede=rede, nome="Ana Antiga", email_user="ana@exemplo.com", status_user="Inativo"
    )
    cliente_logado.post(
        reverse("gestao:importar"),
        {
            "acao": "analisar",
            "tipo": "alunos",
            "atualizar_existentes": "on",
            "arquivo": _upload(ALUNOS_OK),
        },
    )
    cliente_logado.post(
        reverse("gestao:importar"),
        {"acao": "confirmar", "tipo": "alunos", "atualizar_existentes": "on"},
    )
    ana = Usuario.todos.get(email_user="ana@exemplo.com")
    assert ana.nome == "Ana Lima"
    assert Usuario.todos.filter(rede=rede).count() == 3


def test_planilha_sem_coluna_nome_e_recusada(cliente_logado, rede):
    conteudo = "email;telefone\nx@y.com;51\n"
    resposta = cliente_logado.post(
        reverse("gestao:importar"),
        {"acao": "analisar", "tipo": "alunos", "arquivo": _upload(conteudo)},
    )
    assert "coluna de nome" in resposta.context["resultado"].erro_geral


def test_importacao_de_professores(cliente_logado, rede):
    conteudo = CABECALHO + "Professor Um;prof1@exemplo.com;51;;;Ativo\n"
    cliente_logado.post(
        reverse("gestao:importar"),
        {"acao": "analisar", "tipo": "professores", "arquivo": _upload(conteudo)},
    )
    cliente_logado.post(reverse("gestao:importar"), {"acao": "confirmar", "tipo": "professores"})
    assert Professor.todos.filter(rede=rede, nome="Professor Um").exists()


def test_analisar_direto_pelo_servico(db, rede, assinatura_do_tenant):
    resultado = analisar(ALUNOS_OK.encode("utf-8"), "alunos", rede)
    assert resultado.total == 3
    assert resultado.limite == 3
    assert resultado.uso == 0
    assert resultado.excede is False
