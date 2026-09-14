"""Testes do cadastro de professor no dashboard (mesma casca do cadastro de aluno).

Contexto: ate 14/09/2026 ``/professores/`` e ``/professores/novo/`` apenas redirecionavam
para o painel de gestao (Tailwind), o que deixava o cadastro de professor com outra cara.
A protecao por papel foi preservada: quem nao tem o modulo PROFESSORES recebe 403.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from core.models import Unidade, VinculoUsuario
from core.papeis import Papel
from professores.models import Professor


@pytest.fixture
def filial(db, rede):
    return Unidade.todos.create(rede=rede, nome="Unidade Filial", codigo="filial")


def _dados_de_cadastro(unidades, **extra):
    dados = {
        "nome": "Professor Teste",
        "data_nasc": "1990-01-01",
        "cpf_cnpj_prof": "12345678900",
        "email_prof": "professor.teste@exemplo.com",
        "telefone_prof": "(51) 99999-0000",
        "endereco_prof": "Rua Um",
        "numero_end_prof": "10",
        "bairro_prof": "Centro",
        "cep_prof": "90000-000",
        "status_prof": "Ativo",
        "criar_login": "on",
        "senha": "",
        "valor_por_hora": "50.00",
        "unidades": [str(unidade.pk) for unidade in unidades],
    }
    dados.update(extra)
    return dados


def test_lista_de_professores_atende_no_dashboard(db, cliente_logado, rede, unidade):
    Professor.todos.create(rede=rede, unidade=unidade, nome="Ana Professora", status_prof="Ativo")
    resposta = cliente_logado.get(reverse("professor_list"))
    assert resposta.status_code == 200
    assert "Gerenciar Professores" in resposta.content.decode()
    assert "Ana Professora" in resposta.content.decode()


def test_formulario_usa_a_casca_do_cadastro_de_aluno(db, cliente_logado):
    html = cliente_logado.get(reverse("professor_create")).content.decode()
    # mesmo cabecalho do formulario de aluno (usuarios/usuario_form.html)
    assert "card-header bg-primary text-white" in html
    # nada da casca do painel de gestao
    assert "cdn.tailwindcss.com" not in html
    assert "form-control" in html


def test_cadastro_cria_acesso_vinculos_e_valor_da_hora(db, cliente_logado, rede, unidade, filial):
    resposta = cliente_logado.post(
        reverse("professor_create"), _dados_de_cadastro([unidade, filial])
    )
    assert resposta.status_code == 302
    assert resposta["Location"] == reverse("professor_list")

    professor = Professor.todos.get(nome="Professor Teste")
    assert professor.rede_id == rede.pk
    assert professor.user_id is not None
    assert professor.user.is_professor is True
    assert professor.email_prof == "professor.teste@exemplo.com"
    assert professor.valor_por_hora == Decimal("50.00")

    vinculos = VinculoUsuario.todos.filter(usuario=professor.user, papel=Papel.PROFESSOR, ativo=True)
    assert {v.unidade_id for v in vinculos} == {unidade.pk, filial.pk}


def test_cadastro_exige_ao_menos_uma_unidade_de_atendimento(db, cliente_logado, rede, unidade):
    resposta = cliente_logado.post(reverse("professor_create"), _dados_de_cadastro([]))
    assert resposta.status_code == 200
    assert "Escolha ao menos uma unidade de atendimento" in resposta.content.decode()
    assert Professor.todos.count() == 0


def test_email_de_professor_ja_cadastrado_e_recusado(db, cliente_logado, rede, unidade, usuario):
    usuario.is_professor = True
    usuario.email = "repetido@exemplo.com"
    usuario.username = "repetido@exemplo.com"
    usuario.save()
    Professor.todos.create(rede=rede, unidade=unidade, nome="Ja Existe", user=usuario)

    dados = _dados_de_cadastro([unidade], email_prof="repetido@exemplo.com", nome="Outro Nome")
    resposta = cliente_logado.post(reverse("professor_create"), dados)
    assert resposta.status_code == 200
    assert "ja tem cadastro de professor" in resposta.content.decode()
    assert Professor.todos.count() == 1


def test_aluno_nao_acessa_o_cadastro_de_professores(db, rede, unidade):
    aluno = get_user_model().objects.create_user(
        username="aluno.teste", password="senha-de-teste-123", is_student=True
    )
    VinculoUsuario.todos.create(usuario=aluno, rede=rede, unidade=unidade, papel=Papel.ALUNO)
    from django.test import Client

    cliente = Client()
    cliente.force_login(aluno)
    assert cliente.get(reverse("professor_list")).status_code == 403
    assert cliente.get(reverse("professor_create")).status_code == 403


def test_lista_nao_mostra_professor_de_outra_rede(
    db, cliente_logado, rede, unidade, outra_rede, unidade_da_outra_rede
):
    Professor.todos.create(rede=rede, unidade=unidade, nome="Da Minha Rede", status_prof="Ativo")
    Professor.todos.create(
        rede=outra_rede, unidade=unidade_da_outra_rede, nome="De Outra Rede", status_prof="Ativo"
    )
    html = cliente_logado.get(reverse("professor_list")).content.decode()
    assert "Da Minha Rede" in html
    assert "De Outra Rede" not in html


def test_arquivar_professor_tira_da_lista_e_preserva_historico(db, cliente_logado, rede, unidade):
    professor = Professor.todos.create(
        rede=rede, unidade=unidade, nome="Sai da Lista", status_prof="Ativo"
    )
    confirmacao = cliente_logado.get(reverse("professor_delete", args=[professor.pk]))
    assert confirmacao.status_code == 200
    assert "Sai da Lista" in confirmacao.content.decode()

    resposta = cliente_logado.post(reverse("professor_delete", args=[professor.pk]))
    assert resposta.status_code == 302
    professor.refresh_from_db()
    assert professor.arquivado_em is not None
    listagem = cliente_logado.get(reverse("professor_list"))
    assert "Sai da Lista" not in [p.nome for p in listagem.context["professores"]]


def test_edicao_abre_com_as_unidades_atuais(db, cliente_logado, rede, unidade, filial):
    pessoa = get_user_model().objects.create_user(
        username="editar@exemplo.com", is_professor=True
    )
    professor = Professor.todos.create(rede=rede, unidade=unidade, nome="Editar Eu", user=pessoa)
    VinculoUsuario.todos.create(
        usuario=pessoa, rede=rede, unidade=filial, papel=Papel.PROFESSOR, ativo=True
    )
    resposta = cliente_logado.get(reverse("professor_update", args=[professor.pk]))
    assert resposta.status_code == 200
    html = resposta.content.decode()
    assert "Editar Professor" in html
    assert "checked" in html  # a unidade atual do professor vem marcada
