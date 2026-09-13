"""Isolamento entre redes e entre unidades nas telas do painel."""
from __future__ import annotations

import pytest
from django.urls import reverse

from core.models import ConviteEquipe, Unidade
from financeiro.models import Pagamento
from usuarios.models import Usuario


def _aluno(rede, nome, **extra):
    dados = {"rede": rede, "nome": nome, "email_user": f"{nome.split()[0].lower()}@exemplo.com",
             "telefone_user": "51000000000", "status_user": "Ativo"}
    dados.update(extra)
    return Usuario.todos.create(**dados)


def test_lista_nao_mostra_aluno_de_outra_rede(cliente_logado, rede, outra_rede, aluno_da_rede):
    _aluno(outra_rede, "Aluno De Fora")
    resposta = cliente_logado.get(reverse("gestao:alunos"))
    nomes = [a.nome for a in resposta.context["object_list"]]
    assert "Aluno Um" in nomes
    assert "Aluno De Fora" not in nomes


def test_detalhe_de_aluno_de_outra_rede_da_404(cliente_logado, outra_rede):
    de_fora = _aluno(outra_rede, "Aluno De Fora")
    resposta = cliente_logado.get(reverse("gestao:aluno_detalhe", args=[de_fora.pk]))
    assert resposta.status_code == 404


def test_editar_aluno_de_outra_rede_da_404(cliente_logado, outra_rede):
    de_fora = _aluno(outra_rede, "Aluno De Fora")
    resposta = cliente_logado.get(reverse("gestao:aluno_editar", args=[de_fora.pk]))
    assert resposta.status_code == 404


def test_arquivar_aluno_de_outra_rede_da_404(cliente_logado, outra_rede):
    de_fora = _aluno(outra_rede, "Aluno De Fora")
    resposta = cliente_logado.post(reverse("gestao:aluno_arquivar", args=[de_fora.pk]))
    assert resposta.status_code == 404
    de_fora.refresh_from_db()
    assert de_fora.arquivado_em is None


def test_kpis_nao_contam_outra_rede(cliente_logado, rede, outra_rede, aluno_da_rede):
    _aluno(outra_rede, "Aluno De Fora")
    resposta = cliente_logado.get(reverse("gestao:visao_geral"))
    assert resposta.context["alunos_total"] == 1


def test_pagamento_de_outra_rede_nao_aparece(cliente_logado, outra_rede, aluno_user):
    Pagamento.todos.create(
        rede=outra_rede, usuario=aluno_user, valor_pago="99.00",
        data_inicio="2026-09-01", data_fim="2026-09-30", status="pago",
    )
    resposta = cliente_logado.get(reverse("gestao:pagamentos"))
    assert list(resposta.context["object_list"]) == []


def test_convite_de_outra_rede_nao_aparece(cliente_logado, outra_rede):
    ConviteEquipe.objects.create(
        rede=outra_rede, email="estranho@exemplo.com", papel="recepcao",
        token=ConviteEquipe.gerar_token(), expira_em="2030-01-01T00:00:00Z",
    )
    resposta = cliente_logado.get(reverse("gestao:equipe"))
    assert [c.email for c in resposta.context["convites"]] == []


def test_auditoria_de_outra_rede_nao_aparece(cliente_logado, outra_rede):
    from api.models import RegistroAuditoria

    RegistroAuditoria.objects.create(rede=outra_rede, acao="criar", entidade="plano",
                                     descricao="evento de outra rede")
    resposta = cliente_logado.get(reverse("gestao:auditoria"))
    assert [r.descricao for r in resposta.context["object_list"]] == []


def test_recepcao_nao_ve_aluno_de_outra_unidade_da_mesma_rede(
    cliente_recepcao, rede, unidade, usuario
):
    """Dentro da mesma rede, quem opera unidade nao enxerga a outra unidade."""
    filial = Unidade.todos.create(rede=rede, nome="Filial", codigo="filial")
    _aluno(rede, "Aluno do Centro", unidade=unidade)
    _aluno(rede, "Aluno da Filial", unidade=filial)
    resposta = cliente_recepcao.get(reverse("gestao:alunos"))
    nomes = [a.nome for a in resposta.context["object_list"]]
    assert "Aluno do Centro" in nomes
    assert "Aluno da Filial" not in nomes
