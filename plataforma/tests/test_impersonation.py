"""Suporte com impersonation: motivo, auditoria, banner e limites de acesso."""

from __future__ import annotations

import pytest
from django.urls import reverse

from api.models import RegistroAuditoria
from plataforma.models import Impersonacao
from usuarios.models import Usuario


@pytest.fixture
def aluno_com_ficha(db, rede, usuario):
    return Usuario.todos.create(
        rede=rede,
        user=usuario,
        nome="Aluno Suporte",
        email_user="aluno.suporte@exemplo.com",
        telefone_user="51",
        status_user="Ativo",
    )


def test_equipe_da_plataforma_sem_vinculo_nao_entra_no_painel(cliente_plataforma):
    assert cliente_plataforma.get(reverse("gestao:visao_geral")).status_code == 403


def test_impersonation_libera_o_acesso_e_registra(db, cliente_plataforma, suporte, rede):
    resposta = cliente_plataforma.post(
        reverse("plataforma:impersonar", args=[rede.pk]),
        {"motivo": "Cliente relatou erro ao lancar pagamento"},
    )
    assert resposta.status_code == 302
    registro = Impersonacao.objects.get(rede=rede)
    assert registro.usuario_plataforma == suporte
    assert registro.ativa is True
    assert registro.motivo.startswith("Cliente relatou")
    assert RegistroAuditoria.objects.filter(acao="impersonar").exists()

    painel = cliente_plataforma.get(reverse("gestao:visao_geral"))
    assert painel.status_code == 200
    assert "Acesso de suporte em andamento" in painel.content.decode()


def test_impersonation_exige_motivo(db, cliente_plataforma, rede):
    cliente_plataforma.post(reverse("plataforma:impersonar", args=[rede.pk]), {"motivo": "   "})
    assert not Impersonacao.objects.exists()


def test_impersonation_respeita_a_rede_do_cliente(db, cliente_plataforma, rede, outra_rede):
    """Durante o suporte, o contexto e a rede do cliente (nao a rede padrao)."""
    cliente_plataforma.post(
        reverse("plataforma:impersonar", args=[rede.pk]), {"motivo": "conferir dados"}
    )
    resposta = cliente_plataforma.get(reverse("gestao:visao_geral"))
    assert resposta.context["rede"].pk == rede.pk


def test_ficha_de_saude_fica_fora_do_acesso_de_suporte(
    db, cliente_plataforma, rede, aluno_com_ficha
):
    cliente_plataforma.post(reverse("plataforma:impersonar", args=[rede.pk]), {"motivo": "suporte"})
    detalhe = cliente_plataforma.get(reverse("gestao:aluno_detalhe", args=[aluno_com_ficha.pk]))
    assert detalhe.status_code == 200
    assert "não fica disponível durante o acesso de suporte" in detalhe.content.decode()

    envio = cliente_plataforma.post(
        reverse("gestao:aluno_detalhe", args=[aluno_com_ficha.pk]),
        {"altura": "1.80", "peso": "80", "usa_medicamento": "on"},
    )
    assert envio.status_code == 403


def test_sair_da_impersonation_encerra_e_corta_o_acesso(db, cliente_plataforma, rede):
    cliente_plataforma.post(reverse("plataforma:impersonar", args=[rede.pk]), {"motivo": "suporte"})
    resposta = cliente_plataforma.post(reverse("plataforma:sair_impersonacao"))
    assert resposta.status_code == 302
    registro = Impersonacao.objects.get(rede=rede)
    assert registro.fim is not None
    assert cliente_plataforma.get(reverse("gestao:visao_geral")).status_code == 403


def test_auditoria_conta_as_acoes_do_suporte(db, cliente_plataforma, rede):
    cliente_plataforma.post(reverse("plataforma:impersonar", args=[rede.pk]), {"motivo": "suporte"})
    assert RegistroAuditoria.objects.filter(acao="impersonar", entidade="rede").exists()
