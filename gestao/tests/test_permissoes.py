"""Matriz de permissoes do painel (RBAC)."""
from __future__ import annotations

import pytest

from core.papeis import Papel
from gestao.permissoes import MATRIZ, Modulo, NIVEIS, nivel, nivel_do_papel, pode, modulos_visiveis

TODOS = [m.value for m in Modulo]


@pytest.mark.parametrize("modulo", TODOS)
def test_superadmin_da_plataforma_tem_nivel_maximo(modulo):
    assert nivel_do_papel(Papel.SUPERADMIN_PLATAFORMA, modulo) == NIVEIS["admin"]


@pytest.mark.parametrize("modulo", TODOS)
def test_admin_da_rede_tem_nivel_maximo(modulo):
    assert nivel_do_papel(Papel.ADMIN_REDE, modulo) == NIVEIS["admin"]


@pytest.mark.parametrize("modulo", TODOS)
def test_aluno_nao_acessa_o_painel(modulo):
    assert nivel_do_papel(Papel.ALUNO, modulo) == NIVEIS[None]


@pytest.mark.parametrize(
    "papel,modulo,esperado",
    [
        (Papel.RECEPCAO, Modulo.ALUNOS, "editar"),
        (Papel.RECEPCAO, Modulo.AGENDA, "editar"),
        (Papel.RECEPCAO, Modulo.FINANCEIRO, "ver"),
        (Papel.RECEPCAO, Modulo.AUDITORIA, None),
        (Papel.RECEPCAO, Modulo.EQUIPE, None),
        (Papel.PROFESSOR, Modulo.AULAS, "editar"),
        (Papel.PROFESSOR, Modulo.ALUNOS, "ver"),
        (Papel.PROFESSOR, Modulo.FINANCEIRO, None),
        (Papel.FINANCEIRO_REDE, Modulo.FINANCEIRO, "editar"),
        (Papel.FINANCEIRO_REDE, Modulo.AULAS, None),
        (Papel.GESTOR_UNIDADE, Modulo.ALUNOS, "editar"),
        (Papel.GESTOR_UNIDADE, Modulo.AUDITORIA, "ver"),
        (Papel.AUDITOR_REDE, Modulo.AUDITORIA, "ver"),
        (Papel.AUDITOR_REDE, Modulo.FINANCEIRO, "ver"),
        (Papel.AUDITOR_REDE, Modulo.ALUNOS, "ver"),
    ],
)
def test_matriz_por_papel(papel, modulo, esperado):
    assert nivel_do_papel(papel, modulo) == NIVEIS[esperado]


def test_auditor_nao_edita_nada():
    """O papel de auditor e somente leitura em todos os modulos."""
    assert all(
        nivel_do_papel(Papel.AUDITOR_REDE, modulo) <= NIVEIS["ver"] for modulo in TODOS
    )


def test_papel_desconhecido_nao_tem_acesso():
    assert nivel_do_papel("papel.inexistente", Modulo.ALUNOS) == 0


def test_pode_usa_vinculo_ativo_do_usuario(db, usuario, vinculo_admin):
    assert pode(usuario, Modulo.AUDITORIA, "admin")
    assert pode(usuario, Modulo.ALUNOS, "editar")


def test_vinculo_inativo_nao_da_acesso(db, usuario, vinculo_admin):
    vinculo_admin.ativo = False
    vinculo_admin.save(update_fields=["ativo"])
    assert not pode(usuario, Modulo.ALUNOS, "ver")


def test_usuario_de_outra_rede_nao_pode(db, usuario, vinculo_admin, outra_rede):
    """O mesmo usuario, visto pelo contexto da outra rede, nao tem nivel nenhum."""
    assert nivel(usuario, Modulo.ALUNOS, rede=outra_rede) == 0


def test_admin_da_rede_ve_todos_os_modulos(db, usuario, vinculo_admin):
    assert len(modulos_visiveis(usuario)) == len(Modulo)


def test_recepcao_ve_menos_modulos_que_admin(db, recepcionista, usuario, vinculo_admin):
    assert len(modulos_visiveis(recepcionista)) < len(modulos_visiveis(usuario))


def test_professor_nao_ve_financeiro(professor_user):
    assert Modulo.FINANCEIRO not in modulos_visiveis(professor_user)


def test_matriz_nao_tem_modulo_orfao():
    """Todo modulo precisa estar na matriz de pelo menos um papel de rede."""
    papeis = [Papel.ADMIN_REDE, Papel.SUPERADMIN_PLATAFORMA]
    for modulo in Modulo:
        assert any(modulo.value in MATRIZ[papel] for papel in papeis)
