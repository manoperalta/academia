"""Compra de pacote nasce DESABILITADA e e ligada pelo Django admin (requisito de produto)."""

from __future__ import annotations

import pytest
from django.contrib import admin
from django.urls import reverse

from plataforma.models import ConfiguracaoPlataforma, Fatura
from plataforma.servicos import (
    CadastroError,
    cadastrar_tenant_publico,
    compra_de_pacote_liberada,
    espaco_disponivel,
    limite_de_armazenamento,
)

from .conftest import criar_assinatura

pytestmark = pytest.mark.django_db


def _cadastro(**extra):
    dados = {
        "nome": "Academia Toggle",
        "slug": "academia-toggle",
        "cnpj": "",
        "responsavel": "Dono Toggle",
        "email": "dono@toggle.com.br",
        "telefone": "51999998877",
    }
    dados.update(extra)
    return dados


def test_compra_de_pacote_nasce_desabilitada():
    configuracao = ConfiguracaoPlataforma.obter()
    assert configuracao.permitir_compra_de_pacote is False
    assert compra_de_pacote_liberada() is False


def test_interruptor_liga_a_compra():
    configuracao = ConfiguracaoPlataforma.obter()
    configuracao.permitir_compra_de_pacote = True
    configuracao.save(update_fields=["permitir_compra_de_pacote"])
    assert compra_de_pacote_liberada() is True


def test_cadastro_com_pagamento_e_recusado_com_a_compra_desligada(pacote_ouro):
    with pytest.raises(CadastroError) as erro:
        cadastrar_tenant_publico(**_cadastro(), pacote=pacote_ouro, modalidade="pagamento")
    assert "desabilitada" in str(erro.value)
    assert not Fatura.objects.exists()


def test_cadastro_em_trial_continua_funcionando_com_a_compra_desligada(pacote_ouro):
    resultado = cadastrar_tenant_publico(
        **_cadastro(), pacote=pacote_ouro, modalidade="trial"
    )
    assert resultado["rede"].status == "trial"
    assert resultado["assinatura"].pacote == pacote_ouro
    assert resultado["fatura"] is None


def test_com_a_compra_ligada_o_pagamento_gera_fatura(pacote_ouro):
    configuracao = ConfiguracaoPlataforma.obter()
    configuracao.permitir_compra_de_pacote = True
    configuracao.save(update_fields=["permitir_compra_de_pacote"])
    resultado = cadastrar_tenant_publico(
        **_cadastro(slug="academia-toggle-pago"), pacote=pacote_ouro, modalidade="pagamento"
    )
    assert resultado["fatura"] is not None
    assert Fatura.objects.filter(rede=resultado["rede"]).exists()


def test_o_toggle_esta_no_django_admin():
    assert ConfiguracaoPlataforma in admin.site._registry
    modelo_admin = admin.site._registry[ConfiguracaoPlataforma]
    assert "permitir_compra_de_pacote" in modelo_admin.get_fields(request=None) or any(
        "permitir_compra_de_pacote" in campos
        for _, opcoes in modelo_admin.get_fieldsets(request=None)
        for campos in [opcoes.get("fields", ())]
    )
    # o singleton nao pode ser apagado nem duplicado pelo admin
    assert modelo_admin.has_delete_permission(request=None) is False


def test_troca_de_pacote_no_painel_e_bloqueada_com_a_compra_desligada(
    client, usuario, vinculo_admin, rede, pacote_prata, pacote_ouro
):
    criar_assinatura(rede, pacote_prata)
    client.force_login(usuario)
    resposta = client.post(reverse("gestao:plano_mudar", args=[pacote_ouro.pk]))
    assert resposta.status_code == 302
    assinatura = rede.assinatura
    assinatura.refresh_from_db()
    assert assinatura.pacote_id == pacote_prata.pk, "nada muda com a compra desabilitada"


def test_armazenamento_do_pacote_vira_bytes(rede, pacote_prata):
    assert limite_de_armazenamento(rede) is None  # sem assinatura, sem teto
    pacote_prata.limite_armazenamento_gb = 50
    pacote_prata.save(update_fields=["limite_armazenamento_gb"])
    criar_assinatura(rede, pacote_prata)
    assert limite_de_armazenamento(rede) == 50 * 1024**3
    cabe, _ = espaco_disponivel(rede, bytes_novos=1024**2)
    assert cabe is True
