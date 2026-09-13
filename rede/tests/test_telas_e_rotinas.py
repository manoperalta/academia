"""Telas do painel da rede e as rotinas periodicas (jobs com dry-run)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.core.management import call_command
from django.urls import reverse

from governanca.models import RotinaAgendada
from governanca.rotinas import executar_rotinas, sincronizar_rotinas
from rede.models import RegraDeRepasse, Repasse
from rede.servicos import emitir_repasse, periodo_do_mes


@pytest.fixture
def regra(db, rede):
    return RegraDeRepasse.objects.create(
        rede=rede, unidade=None, tipo=RegraDeRepasse.Tipo.PERCENTUAL, percentual=Decimal("8.000")
    )


def test_painel_da_rede_abre_com_comparativo(cliente_rede, unidades, receita):
    resposta = cliente_rede.get(reverse("rede:painel"))
    assert resposta.status_code == 200
    conteudo = resposta.content.decode()
    assert "Comparativo entre unidades" in conteudo and "Unidade Centro" in conteudo


def test_telas_da_rede_abrem(cliente_rede, unidades, receita, regra):
    rotas = [
        "rede:painel",
        "rede:unidades",
        "rede:metas",
        "rede:repasses",
        "rede:regras",
        "rede:governanca",
        "rede:comunicados",
        "rede:aprovacoes",
        "rede:catalogo",
        "rede:transferencias",
        "rede:importar",
        "rede:unidade_template",
        "rede:unidade_criar",
        "rede:meta_criar",
        "rede:regra_criar",
        "rede:comunicado_criar",
    ]
    for rota in rotas:
        assert cliente_rede.get(reverse(rota)).status_code == 200, rota


def test_demonstrativo_do_repasse_abre_e_confere(cliente_rede, unidades, receita, regra):
    repasse = emitir_repasse(unidades[0], *periodo_do_mes())
    resposta = cliente_rede.get(reverse("rede:repasse_detalhe", args=[repasse.pk]))
    assert resposta.status_code == 200
    conteudo = resposta.content.decode()
    assert "Memória de cálculo" in conteudo and "reproduz exatamente" in conteudo
    csv_resposta = cliente_rede.get(reverse("rede:repasse_csv", args=[repasse.pk]))
    assert csv_resposta.status_code == 200
    assert "Total devido" in csv_resposta.content.decode()


def test_cliente_da_unidade_nao_entra_na_governanca(cliente_da_unidade):
    assert cliente_da_unidade.get(reverse("rede:governanca")).status_code == 403
    assert cliente_da_unidade.get(reverse("rede:painel")).status_code == 200


def test_previa_do_repasse_nao_grava(cliente_rede, unidades, receita, regra):
    resposta = cliente_rede.post(reverse("rede:repasse_acao"), {"acao": "previa"})
    assert resposta.status_code == 302
    assert Repasse.objects.count() == 0


def test_emissao_pela_tela(cliente_rede, unidades, receita, regra):
    resposta = cliente_rede.post(reverse("rede:repasse_acao"), {"acao": "emitir"})
    assert resposta.status_code == 302
    assert Repasse.objects.count() == 3


def test_transferencia_pela_tela_exige_confirmacao(cliente_rede, unidades, receita):
    resposta = cliente_rede.post(
        reverse("rede:transferencias"),
        {
            "origem": unidades[0].pk,
            "destino": unidades[1].pk,
            "confirmacao": "nao",
        },
    )
    assert resposta.status_code == 302
    from usuarios.models import Usuario

    assert Usuario.todos.filter(unidade=unidades[0]).count() > 0  # nada mudou
    certo = cliente_rede.post(
        reverse("rede:transferencias"),
        {
            "origem": unidades[0].pk,
            "destino": unidades[1].pk,
            "motivo": "teste",
            "confirmacao": "TRANSFERIR",
        },
    )
    assert certo.status_code == 302
    assert Usuario.todos.filter(unidade=unidades[0]).count() == 0


def test_rotinas_sincronizam_e_rodam_em_dry_run(db):
    criadas = sincronizar_rotinas()
    assert criadas == 9
    resultado = executar_rotinas(dry_run=True)
    assert resultado["dry_run"] is True
    assert {item["rotina"] for item in resultado["executadas"]} >= {
        "metricas",
        "backup",
        "repasses",
    }
    assert all(item["simulado"] for item in resultado["executadas"])
    # dry-run nao marca a rotina como executada
    assert RotinaAgendada.objects.filter(ultima_execucao__isnull=True).count() == 9


def test_rotina_de_metas_e_atrasos_rodam_de_verdade(db, rede, unidades, receita, regra):
    sincronizar_rotinas()
    resultado = executar_rotinas(somente="metas")
    metas = [item for item in resultado["executadas"] if item["rotina"] == "metas"]
    assert metas and metas[0]["situacao"] == RotinaAgendada.Situacao.OK
    rotina = RotinaAgendada.objects.get(nome="metas")
    assert rotina.ultima_execucao is not None and rotina.ultima_situacao == "ok"
    atrasos = executar_rotinas(somente="atrasos")
    assert atrasos["executadas"][0]["situacao"] == RotinaAgendada.Situacao.OK


def test_rotina_que_falha_fica_registrada(db, monkeypatch):
    sincronizar_rotinas()
    import governanca.rotinas as rotinas

    def explodir(dry_run):
        raise RuntimeError("sem espaco em disco")

    monkeypatch.setitem(rotinas.ROTINAS, "backup", ("dia", "backup", explodir))
    resultado = executar_rotinas(somente="backup")
    assert resultado["falhas"], "a falha precisa aparecer no resultado"
    rotina = RotinaAgendada.objects.get(nome="backup")
    assert rotina.ultima_situacao == RotinaAgendada.Situacao.FALHOU
    assert "sem espaco" in rotina.ultimo_resultado


def test_comando_de_rotinas(db, capsys):
    call_command("executar_rotinas", "--dry-run")
    saida = capsys.readouterr().out
    assert "[SIMULA]" in saida and "backup" in saida
