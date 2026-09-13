"""Telas do painel do tenant: acesso, CRUD e auditoria."""

from __future__ import annotations

import pytest
from django.conf import settings
from django.urls import reverse

from api.models import RegistroAuditoria
from financeiro.models import Pagamento
from gestao.permissoes import Modulo
from usuarios.models import Usuario

TELAS_DO_ADMIN = [
    "gestao:visao_geral",
    "gestao:alunos",
    "gestao:professores",
    "gestao:aulas",
    "gestao:agenda",
    "gestao:financeiro",
    "gestao:planos",
    "gestao:pagamentos",
    "gestao:despesas",
    "gestao:relatorios",
    "gestao:comunicacao",
    "gestao:identidade",
    "gestao:equipe",
    "gestao:auditoria",
    "gestao:onboarding",
]


@pytest.mark.parametrize("rota", TELAS_DO_ADMIN)
def test_admin_da_rede_abre_todas_as_telas(cliente_logado, rota):
    resposta = cliente_logado.get(reverse(rota))
    assert resposta.status_code == 200, rota


def test_anonimo_e_levado_ao_login(client, db):
    resposta = client.get(reverse("gestao:visao_geral"))
    assert resposta.status_code == 302
    assert settings.LOGIN_URL in resposta["Location"]


def test_usuario_sem_vinculo_recebe_403(cliente_sem_vinculo):
    resposta = cliente_sem_vinculo.get(reverse("gestao:visao_geral"))
    assert resposta.status_code == 403


def test_aluno_nao_entra_no_painel(cliente_aluno):
    assert cliente_aluno.get(reverse("gestao:visao_geral")).status_code == 403


def test_recepcao_nao_ve_auditoria(cliente_recepcao):
    """Recepcao opera alunos e agenda, mas nao acessa auditoria."""
    assert cliente_recepcao.get(reverse("gestao:alunos")).status_code == 200
    assert cliente_recepcao.get(reverse("gestao:auditoria")).status_code == 403
    assert cliente_recepcao.get(reverse("gestao:equipe")).status_code == 403


def test_professor_nao_ve_financeiro(cliente_professor):
    assert cliente_professor.get(reverse("gestao:aulas")).status_code == 200
    assert cliente_professor.get(reverse("gestao:financeiro")).status_code == 403


def test_menu_mostra_apenas_modulos_liberados(cliente_recepcao):
    """Recepcao opera alunos/agenda e apenas enxerga o financeiro (sem editar)."""
    resposta = cliente_recepcao.get(reverse("gestao:alunos"))
    menu = {item["modulo"]: item["nivel"] for item in resposta.context["menu_painel"]}
    assert menu[Modulo.ALUNOS] == 2
    assert menu[Modulo.FINANCEIRO] == 1
    assert Modulo.AUDITORIA not in menu
    assert Modulo.EQUIPE not in menu
    assert Modulo.COMUNICACAO not in menu


def test_auditor_tem_acesso_somente_leitura(cliente_logado, usuario, vinculo_admin):
    from core.papeis import Papel

    vinculo_admin.papel = Papel.AUDITOR_REDE
    vinculo_admin.save(update_fields=["papel"])
    assert cliente_logado.get(reverse("gestao:auditoria")).status_code == 200
    # auditor ve a lista, mas nao ganha o botao de criar
    resposta = cliente_logado.get(reverse("gestao:alunos"))
    assert resposta.status_code == 200
    assert resposta.context["pode_editar"] is False


# ------------------------------------------------------------------ CRUD ALUNO
def _dados_aluno(**extra):
    dados = {
        "nome": "Maria da Silva",
        "email_user": "maria@exemplo.com",
        "telefone_user": "51988887777",
        "status_user": "Ativo",
        "criar_login": "on",
        "senha": "",
    }
    dados.update(extra)
    return dados


def test_criar_aluno_cria_acesso_e_auditoria(cliente_logado, rede):
    resposta = cliente_logado.post(reverse("gestao:aluno_novo"), _dados_aluno())
    assert resposta.status_code == 302
    aluno = Usuario.objects.get(nome="Maria da Silva")
    assert aluno.rede_id == rede.pk
    assert aluno.user is not None and aluno.user.is_student is True
    assert aluno.user.username == "maria@exemplo.com"
    assert aluno.user.check_password("") is False  # senha temporaria foi gerada
    assert RegistroAuditoria.objects.filter(entidade="aluno", acao="criar").exists()


def test_criar_aluno_com_senha_definida(cliente_logado):
    cliente_logado.post(reverse("gestao:aluno_novo"), _dados_aluno(senha="SenhaForte123"))
    aluno = Usuario.objects.get(nome="Maria da Silva")
    assert aluno.user.check_password("SenhaForte123")


def test_aluno_sem_nome_nao_e_criado(cliente_logado):
    resposta = cliente_logado.post(reverse("gestao:aluno_novo"), _dados_aluno(nome=""))
    assert resposta.status_code == 200
    assert not Usuario.objects.filter(email_user="maria@exemplo.com").exists()


def test_editar_aluno(cliente_logado, aluno_da_rede):
    resposta = cliente_logado.post(
        reverse("gestao:aluno_editar", args=[aluno_da_rede.pk]),
        _dados_aluno(
            nome="Aluno Renomeado", email_user=aluno_da_rede.email_user, senha="SenhaForte123"
        ),
    )
    assert resposta.status_code == 302
    aluno_da_rede.refresh_from_db()
    assert aluno_da_rede.nome == "Aluno Renomeado"
    assert RegistroAuditoria.objects.filter(entidade="aluno", acao="alterar").exists()


def test_arquivar_aluno_e_soft_delete(cliente_logado, aluno_da_rede):
    cliente_logado.post(reverse("gestao:aluno_arquivar", args=[aluno_da_rede.pk]))
    aluno_da_rede.refresh_from_db()
    assert aluno_da_rede.arquivado_em is not None
    # nao aparece na lista normal
    lista = cliente_logado.get(reverse("gestao:alunos"))
    assert aluno_da_rede.nome not in [a.nome for a in lista.context["object_list"]]
    # aparece quando pedimos os arquivados
    arquivados = cliente_logado.get(reverse("gestao:alunos"), {"arquivados": "1"})
    assert aluno_da_rede.nome in [a.nome for a in arquivados.context["object_list"]]


def test_restaurar_aluno(cliente_logado, aluno_da_rede):
    cliente_logado.post(reverse("gestao:aluno_arquivar", args=[aluno_da_rede.pk]))
    cliente_logado.post(reverse("gestao:aluno_arquivar", args=[aluno_da_rede.pk]))
    aluno_da_rede.refresh_from_db()
    assert aluno_da_rede.arquivado_em is None


def test_busca_por_nome(cliente_logado, aluno_da_rede, rede):
    Usuario.todos.create(
        rede=rede,
        nome="Outro Aluno",
        email_user="outro@exemplo.com",
        telefone_user="51000000000",
        status_user="Ativo",
    )
    resposta = cliente_logado.get(reverse("gestao:alunos"), {"q": "Outro"})
    nomes = [a.nome for a in resposta.context["object_list"]]
    assert nomes == ["Outro Aluno"]


def test_htmx_devolve_apenas_a_tabela(cliente_logado, aluno_da_rede):
    resposta = cliente_logado.get(reverse("gestao:alunos"), HTTP_HX_REQUEST="true")
    conteudo = resposta.content.decode()
    assert "<!doctype html>" not in conteudo.lower()
    assert "Aluno Um" in conteudo


# ------------------------------------------------------------------ DASHBOARD
def test_visao_geral_conta_apenas_ativos(cliente_logado, aluno_da_rede, rede):
    Usuario.todos.create(
        rede=rede,
        nome="Inativo",
        email_user="i@exemplo.com",
        telefone_user="51",
        status_user="Inativo",
    )
    resposta = cliente_logado.get(reverse("gestao:visao_geral"))
    assert resposta.context["alunos_ativos"] == 1
    assert resposta.context["alunos_total"] == 2


def test_assistente_mostra_percentual(cliente_logado):
    resposta = cliente_logado.get(reverse("gestao:onboarding"))
    passos = resposta.context["passos"]
    assert len(passos) >= 8
    assert 0 <= passos[0]["percentual"] <= 100


# ------------------------------------------------------------------ FINANCEIRO
def test_dar_baixa_em_pagamento(cliente_logado, aluno_user, rede):
    pagamento = Pagamento.todos.create(
        rede=rede,
        usuario=aluno_user,
        valor_pago="150.00",
        data_inicio="2026-09-01",
        data_fim="2026-09-30",
        status="pendente",
    )
    resposta = cliente_logado.post(reverse("gestao:pagamento_baixar", args=[pagamento.pk]))
    assert resposta.status_code == 302
    pagamento.refresh_from_db()
    assert pagamento.status == "pago"
    assert pagamento.data_pagamento is not None


def test_exportacao_csv_tem_bom_e_auditoria(cliente_logado, aluno_da_rede):
    resposta = cliente_logado.get(reverse("gestao:relatorio_alunos_csv"))
    assert resposta.status_code == 200
    assert resposta["Content-Type"].startswith("text/csv")
    assert resposta.content.decode("utf-8").startswith("\ufeff")
    assert "Aluno Um" in resposta.content.decode("utf-8")
    assert RegistroAuditoria.objects.filter(entidade="aluno", acao="exportar").exists()


def test_auditoria_lista_so_da_propria_rede(cliente_logado, rede, outra_rede):
    RegistroAuditoria.objects.create(
        rede=outra_rede, acao="criar", entidade="aluno", descricao="de outra rede"
    )
    resposta = cliente_logado.get(reverse("gestao:auditoria"))
    descricoes = [r.descricao for r in resposta.context["object_list"]]
    assert "de outra rede" not in descricoes
