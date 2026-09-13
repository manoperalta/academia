"""Troca de pacote pelo cliente: upgrade imediato, downgrade agendado e limites."""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from plataforma.models import Assinatura, Fatura
from plataforma.servicos import (
    aplicar_trocas_agendadas,
    situacao_do_tenant,
    trocar_pacote_do_tenant,
    uso_do_tenant,
)
from plataforma.tests.conftest import criar_alunos, criar_assinatura


@pytest.fixture
def cliente_recepcao(db, rede):
    """Usuario de recepcao (nao pode mexer no plano)."""
    from django.contrib.auth import get_user_model
    from django.test import Client

    from core.models import VinculoUsuario

    usuario = get_user_model().objects.create_user(
        username="recepcao.teste",
        password="SenhaRecepcao123",
        email="recepcao@exemplo.com",
    )
    VinculoUsuario.todos.create(
        usuario=usuario, rede=rede, unidade=None, papel="recepcao", ativo=True
    )
    cliente = Client()
    cliente.force_login(usuario)
    return cliente


def test_upgrade_imediato_gera_fatura_proporcional(db, rede, pacote_prata, pacote_ouro):
    assinatura = criar_assinatura(rede, pacote_prata)
    resultado = trocar_pacote_do_tenant(rede, pacote_ouro)
    assinatura.refresh_from_db()
    assert assinatura.pacote == pacote_ouro
    assert resultado["tipo"] == "upgrade"
    fatura = Fatura.objects.get(rede=rede)
    assert fatura.valor_final > Decimal("0")
    assert fatura.pix_copia_cola
    assert "proporcional" in fatura.observacao.lower()


def test_downgrade_fica_agendado_e_avisa_o_excesso(db, rede, pacote_bronze, pacote_prata):
    assinatura = criar_assinatura(rede, pacote_bronze)
    criar_alunos(rede, 140)  # acima do limite do Prata (100)
    resultado = trocar_pacote_do_tenant(rede, pacote_prata)
    assinatura.refresh_from_db()
    assert resultado["tipo"] == "downgrade"
    assert assinatura.pacote == pacote_bronze  # ainda nao mudou
    assert assinatura.pacote_agendado == pacote_prata  # vale na renovacao
    assert "acima do novo limite" in resultado["aviso"]
    assert "nada e apagado" in resultado["aviso"].lower() or "Nada e apagado" in resultado["aviso"]
    assert uso_do_tenant(rede)["alunos"] == 140


def test_troca_agendada_e_aplicada_na_renovacao(db, rede, pacote_bronze, pacote_prata):
    hoje = timezone.localdate()
    assinatura = criar_assinatura(rede, pacote_bronze, dias=0)
    assinatura.renovacao_em = hoje
    assinatura.save()
    trocar_pacote_do_tenant(rede, pacote_prata)
    assert aplicar_trocas_agendadas(hoje) == 1
    assinatura.refresh_from_db()
    assert assinatura.pacote == pacote_prata
    assert assinatura.pacote_agendado is None


def test_trocar_para_o_mesmo_pacote_nao_faz_nada(db, rede, pacote_prata):
    criar_assinatura(rede, pacote_prata)
    resultado = trocar_pacote_do_tenant(rede, pacote_prata)
    assert resultado["tipo"] == "nenhuma"
    assert not Fatura.objects.exists()


def test_downgrade_nao_apaga_dados_e_bloqueia_cadastro(db, rede, pacote_bronze, pacote_prata):
    from plataforma.servicos import pode_cadastrar

    criar_assinatura(rede, pacote_bronze)
    criar_alunos(rede, 140)
    trocar_pacote_do_tenant(rede, pacote_prata)
    # renovacao vencida: aplica a troca agendada sem perder o pacote agendado
    Assinatura.objects.filter(rede=rede).update(renovacao_em=timezone.localdate())
    aplicar_trocas_agendadas()
    liberado, mensagem = pode_cadastrar(rede, "alunos")
    assert liberado is False
    assert "Meu plano" in mensagem
    assert uso_do_tenant(rede)["alunos"] == 140  # nada apagado


def test_cliente_troca_pacote_pelo_painel(cliente_logado, rede, pacote_prata, pacote_ouro):
    from plataforma.models import ConfiguracaoPlataforma

    # A compra de pacote nasce desabilitada; esta tela so opera com ela habilitada.
    configuracao = ConfiguracaoPlataforma.obter()
    configuracao.permitir_compra_de_pacote = True
    configuracao.save(update_fields=["permitir_compra_de_pacote"])

    criar_assinatura(rede, pacote_prata)
    resposta = cliente_logado.post(reverse("gestao:plano_mudar", args=[pacote_ouro.pk]))
    assert resposta.status_code == 302
    assert Fatura.objects.filter(rede=rede).exists()


def test_recepcao_nao_troca_pacote(cliente_recepcao, rede, pacote_prata, pacote_ouro):
    criar_assinatura(rede, pacote_prata)
    resposta = cliente_recepcao.post(reverse("gestao:plano_mudar", args=[pacote_ouro.pk]))
    assert resposta.status_code == 403


def test_situacao_mostra_pacote_agendado(db, rede, pacote_bronze, pacote_prata):
    criar_assinatura(rede, pacote_bronze)
    trocar_pacote_do_tenant(rede, pacote_prata)
    situacao = situacao_do_tenant(rede)
    assert situacao["assinatura"].pacote_agendado == pacote_prata
