"""Telas do painel da plataforma: acesso restrito e acoes principais."""

from __future__ import annotations

import pytest
from django.urls import reverse

from core.models import Rede
from plataforma.models import Assinatura, ConfiguracaoPlataforma, Pacote

TELAS = [
    "plataforma:metricas",
    "plataforma:tenants",
    "plataforma:pacotes",
    "plataforma:faturas",
    "plataforma:regua",
    "plataforma:webhooks",
    "plataforma:relatorio",
    "plataforma:config",
]


@pytest.mark.parametrize("rota", TELAS)
def test_equipe_abre_as_telas(cliente_plataforma, rota):
    assert cliente_plataforma.get(reverse(rota)).status_code == 200


def test_anonimo_vai_para_o_login(client, db):
    resposta = client.get(reverse("plataforma:metricas"))
    assert resposta.status_code == 302


def test_usuario_do_tenant_nao_entra(cliente_logado):
    assert cliente_logado.get(reverse("plataforma:metricas")).status_code == 403


def test_criar_tenant_pelo_painel(cliente_plataforma, pacote_prata):
    resposta = cliente_plataforma.post(
        reverse("plataforma:tenant_novo"),
        {
            "nome": "Academia Nova",
            "slug": "academia-nova",
            "pacote": pacote_prata.pk,
            "ciclo": "mensal",
            "cnpj": "12345678000199",
            "email": "dono@academia.com",
            "telefone": "51999999999",
            "trial": "on",
        },
    )
    assert resposta.status_code == 302
    rede = Rede.todos.get(slug="academia-nova")
    assert rede.status == "trial"
    assinatura = Assinatura.objects.get(rede=rede)
    assert assinatura.pacote == pacote_prata
    assert assinatura.em_trial is True


def test_suspender_e_reativar_cliente(cliente_plataforma, rede, assinatura):
    cliente_plataforma.post(reverse("plataforma:tenant_acao", args=[rede.pk, "suspender"]))
    rede.refresh_from_db()
    assert rede.status == "suspenso"
    cliente_plataforma.post(reverse("plataforma:tenant_acao", args=[rede.pk, "reativar"]))
    rede.refresh_from_db()
    assert rede.status == "ativo"


def test_ficha_do_cliente_mostra_uso_e_faturas(cliente_plataforma, rede, assinatura):
    resposta = cliente_plataforma.get(reverse("plataforma:tenant_ficha", args=[rede.pk]))
    assert resposta.status_code == 200
    assert resposta.context["situacao"]["limites"]["alunos"] == 100


def test_editar_cliente_com_excecao_comercial(cliente_plataforma, rede, assinatura, pacote_prata):
    resposta = cliente_plataforma.post(
        reverse("plataforma:tenant_editar", args=[rede.pk]),
        {
            "nome": "Academia Renomeada",
            "cnpj": "",
            "email_responsavel": "",
            "telefone": "",
            "dominio": "",
            "observacoes_internas": "Cliente estrategico",
            "pacote": pacote_prata.pk,
            "ciclo": "mensal",
            "limite_alunos_custom": 60,
            "motivo_excecao": "Negociacao comercial aprovada",
        },
    )
    assert resposta.status_code == 302
    rede.refresh_from_db()
    assinatura.refresh_from_db()
    assert rede.nome == "Academia Renomeada"
    assert assinatura.limite_alunos_custom == 60
    assert assinatura.autorizado_por is not None
    assert assinatura.limite_efetivo("alunos") == 60


def test_excecao_sem_motivo_e_recusada(cliente_plataforma, rede, assinatura, pacote_prata):
    resposta = cliente_plataforma.post(
        reverse("plataforma:tenant_editar", args=[rede.pk]),
        {
            "nome": rede.nome,
            "pacote": pacote_prata.pk,
            "ciclo": "mensal",
            "limite_alunos_custom": 60,
            "motivo_excecao": "",
        },
    )
    assert resposta.status_code == 200
    assinatura.refresh_from_db()
    assert assinatura.limite_alunos_custom is None


def test_criar_e_editar_pacote(cliente_plataforma):
    resposta = cliente_plataforma.post(
        reverse("plataforma:pacote_novo"),
        {
            "nome": "Diamante",
            "codigo": "diamante",
            "descricao": "Top",
            "limite_alunos": 300,
            "limite_professores": 20,
            "limite_unidades": 5,
            "preco_mensal": "700.00",
            "preco_anual": "7000.00",
            "ordem_exibicao": 4,
            "visivel_no_site": "on",
            "ativo": "on",
            "modulos": ["api", "whatsapp"],
        },
    )
    assert resposta.status_code == 302
    pacote = Pacote.objects.get(codigo="diamante")
    assert pacote.limite_alunos == 300
    assert pacote.tem_modulo("api") is True


def test_emitir_fatura_pela_ficha(cliente_plataforma, rede, assinatura):
    cliente_plataforma.post(reverse("plataforma:tenant_faturar", args=[rede.pk]))
    fatura = rede.faturas.first()
    assert fatura is not None
    assert fatura.pix_copia_cola
    assert fatura.gateway == "simulado"


def test_rodar_regua_pela_tela(cliente_plataforma, rede, assinatura):
    resposta = cliente_plataforma.post(reverse("plataforma:regua"))
    assert resposta.status_code == 302


def test_configuracao_salva_chave_do_gateway(cliente_plataforma):
    resposta = cliente_plataforma.post(
        reverse("plataforma:config"),
        {
            "nome_emitente": "SafeStack",
            "cnpj_emitente": "123",
            "email_financeiro": "fin@safestack.com.br",
            "asaas_api_key": "chave-de-teste",
            "asaas_ambiente": "sandbox",
            "asaas_base_url": "",
            "token_webhook": "token-de-teste",
            "trial_dias": 14,
            "dias_bloqueio": 10,
            "dias_suspensao": 30,
            "multa_percentual": "2",
            "juros_dia_percentual": "0.033",
            "regua_ativa": "on",
        },
    )
    assert resposta.status_code == 302
    configuracao = ConfiguracaoPlataforma.obter()
    assert configuracao.asaas_api_key == "chave-de-teste"
    assert configuracao.gateway_em_modo_simulado is False


def test_relatorio_csv(cliente_plataforma, rede, assinatura):
    cliente_plataforma.post(reverse("plataforma:tenant_faturar", args=[rede.pk]))
    resposta = cliente_plataforma.get(reverse("plataforma:relatorio_csv"))
    assert resposta.status_code == 200
    conteudo = resposta.content.decode("utf-8")
    assert conteudo.startswith("\ufeff")
    assert "FAT-" in conteudo
