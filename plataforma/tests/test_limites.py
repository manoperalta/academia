"""Limites do pacote: contagem, bloqueio no teto, avisos e feature flags."""

from __future__ import annotations

from django.urls import reverse

from api.models import RegistroAuditoria
from notificacoes.models import ConfiguracaoWhatsapp
from plataforma.models import Assinatura, ModuloPacote
from plataforma.servicos import (
    alertas_de_limite,
    limites_efetivos,
    modulo_disponivel,
    pode_cadastrar,
    situacao_do_tenant,
    uso_do_tenant,
)
from plataforma.tests.conftest import criar_alunos, criar_assinatura
from usuarios.models import Usuario


def test_uso_conta_apenas_cadastros_ativos(db, rede, assinatura):
    criar_alunos(rede, 3, "Ativo")
    criar_alunos(rede, 2, "Inativo")
    assert uso_do_tenant(rede)["alunos"] == 3


def test_limite_efetivo_usa_o_mais_restritivo(db, rede, assinatura):
    assinatura.limite_alunos_custom = 50
    assinatura.save()
    assert assinatura.limite_efetivo("alunos") == 50
    assinatura.limite_alunos_custom = 500
    assinatura.save()
    assert assinatura.limite_efetivo("alunos") == 100


def test_limites_efetivos_e_situacao(db, rede, assinatura):
    criar_alunos(rede, 10)
    limites = limites_efetivos(rede)
    assert limites == {"alunos": 100, "professores": 5, "unidades": 1}
    situacao = situacao_do_tenant(rede)
    assert situacao["uso"]["alunos"] == 10
    assert situacao["recursos"][0]["percentual"] == 10
    assert situacao["alertas"] == []


def test_pode_cadastrar_recusa_no_teto_com_mensagem_acionavel(db, rede, assinatura):
    criar_alunos(rede, 100)
    liberado, mensagem = pode_cadastrar(rede, "alunos")
    assert liberado is False
    assert "100" in mensagem and "Meu plano" in mensagem


def test_pode_cadastrar_libera_abaixo_do_teto(db, rede, assinatura):
    criar_alunos(rede, 99)
    assert pode_cadastrar(rede, "alunos")[0] is True


def test_ouro_nao_tem_teto(db, rede, pacote_ouro):
    criar_assinatura(rede, pacote_ouro)
    criar_alunos(rede, 120)
    assert pode_cadastrar(rede, "alunos")[0] is True
    assert limites_efetivos(rede)["alunos"] is None


def test_avisos_em_80_e_95(db, rede, assinatura):
    criar_alunos(rede, 80)
    assert [a["nivel"] for a in alertas_de_limite(rede)] == ["atencao"]
    criar_alunos(rede, 15)
    assert [a["nivel"] for a in alertas_de_limite(rede)] == ["critico"]


def test_sem_assinatura_nao_bloqueia(db, rede):
    criar_alunos(rede, 200)
    assert pode_cadastrar(rede, "alunos")[0] is True


def test_painel_recusa_cadastro_no_teto(cliente_logado, rede, assinatura):
    criar_alunos(rede, 100)
    resposta = cliente_logado.post(
        reverse("gestao:aluno_novo"),
        {
            "nome": "Aluno Excedente",
            "email_user": "excedente@exemplo.com",
            "telefone_user": "51",
            "status_user": "Ativo",
        },
    )
    assert resposta.status_code == 302
    assert not Usuario.objects.filter(email_user="excedente@exemplo.com").exists()
    assert RegistroAuditoria.objects.filter(acao="limite", entidade="aluno").exists()


def test_painel_permite_cadastro_abaixo_do_teto(cliente_logado, rede, assinatura):
    criar_alunos(rede, 99)
    cliente_logado.post(
        reverse("gestao:aluno_novo"),
        {
            "nome": "Aluno Noventa e Nove",
            "email_user": "ultimo@exemplo.com",
            "telefone_user": "51",
            "status_user": "Ativo",
        },
    )
    assert Usuario.objects.filter(email_user="ultimo@exemplo.com").exists()


def test_exportacao_csv_exige_modulo_do_pacote(cliente_logado, rede, assinatura):
    assert cliente_logado.get(reverse("gestao:relatorio_alunos_csv")).status_code == 403
    assert cliente_logado.get(reverse("gestao:relatorio_pagamentos_csv")).status_code == 403


def test_exportacao_liberada_no_ouro(cliente_logado, rede, pacote_ouro):
    criar_assinatura(rede, pacote_ouro)
    assert cliente_logado.get(reverse("gestao:relatorio_alunos_csv")).status_code == 200


def test_modulo_do_pacote(db, rede, pacote_bronze, pacote_prata):
    criar_assinatura(rede, pacote_prata)
    assert modulo_disponivel(rede, ModuloPacote.WHATSAPP) is False
    assinatura = Assinatura.objects.get(rede=rede)
    assinatura.pacote = pacote_bronze
    assinatura.save()
    assert modulo_disponivel(rede, ModuloPacote.WHATSAPP) is True


def test_whatsapp_bloqueado_sem_modulo(cliente_logado, rede, assinatura):
    resposta = cliente_logado.post(
        reverse("gestao:comunicacao"),
        {
            "whatsapp-access_token": "token-fake",
            "whatsapp-phone_number_id": "123",
            "whatsapp-ativo": "on",
        },
    )
    assert resposta.status_code == 302
    assert not ConfiguracaoWhatsapp.todos.filter(rede=rede).exists()
