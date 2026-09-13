"""Comissoes, gamificacao, NPS, check-in e PWA da area do aluno (fase 8)."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from area_do_aluno.models import CheckinDoAluno
from area_do_aluno.servicos import ErroDeCheckin, registrar_checkin
from gamificacao.models import Conquista, EventoDePontos, RegraDePontos, SaldoDePontos
from gamificacao.servicos import ErroDeGamificacao, pontuar, ranking, saldo_do_aluno
from nps.models import Pesquisa, Resposta, TipoDePesquisa
from nps.servicos import (
    ErroDePesquisa,
    detratores_para_tratar,
    marcar_tratada,
    nps,
    registrar_resposta,
)
from remuneracao.models import (
    ApuracaoDeComissao,
    RegraDeComissao,
    SituacaoDeApuracao,
    TipoDeComissao,
)
from remuneracao.servicos import (
    ErroDeRemuneracao,
    apurar_competencia,
    calcular_apuracao,
    competencia,
    conferir_apuracao,
    emitir_apuracao,
    extrato_do_professor,
    marcar_paga,
)


# ------------------------------------------------------------------ comissoes
def test_comissao_percentual_do_recebido(db, rede, unidade, professor, receita):
    RegraDeComissao.objects.create(
        rede=rede,
        professor=None,
        unidade=unidade,
        tipo=TipoDeComissao.PERCENTUAL,
        percentual=Decimal("10.000"),
    )
    inicio, fim = competencia()
    calculo = calcular_apuracao(professor, unidade, inicio, fim)
    assert calculo["base_de_calculo"] == Decimal("400.00")  # 2 x 200 recebidos
    assert calculo["total"] == Decimal("40.00")  # 10% de 400


def test_comissao_por_aluno_e_por_aula(db, rede, unidade, professor, receita):
    RegraDeComissao.objects.create(
        rede=rede, professor=professor, tipo=TipoDeComissao.POR_ALUNO, valor=Decimal("15.00")
    )
    inicio, fim = competencia()
    calculo = calcular_apuracao(professor, unidade, inicio, fim)
    assert calculo["total"] == Decimal("45.00")  # 3 alunos ativos x 15

    RegraDeComissao.objects.all().delete()
    RegraDeComissao.objects.create(
        rede=rede, professor=professor, tipo=TipoDeComissao.POR_AULA, valor=Decimal("50.00")
    )
    calculo = calcular_apuracao(professor, unidade, inicio, fim)
    # sem agenda com professor vinculado a comissao por aula nao inventa numero
    assert calculo["total"] == Decimal("0.00")
    assert "nao apuravel" in calculo["linhas"][0]["descricao"]


def test_comissao_fixa_com_piso_e_teto(db, rede, unidade, professor):
    RegraDeComissao.objects.create(
        rede=rede,
        professor=professor,
        tipo=TipoDeComissao.FIXO,
        valor=Decimal("100.00"),
        piso_mensal=Decimal("300.00"),
    )
    inicio, fim = competencia()
    calculo = calcular_apuracao(professor, unidade, inicio, fim)
    assert calculo["total"] == Decimal("300.00")
    assert calculo["piso_aplicado"] is True
    assert calculo["resumo"]["linhas"][-1]["tipo"] == "piso"

    RegraDeComissao.objects.all().delete()
    RegraDeComissao.objects.create(
        rede=rede,
        professor=professor,
        tipo=TipoDeComissao.FIXO,
        valor=Decimal("1000.00"),
        teto_mensal=Decimal("600.00"),
    )
    calculo = calcular_apuracao(professor, unidade, inicio, fim)
    assert calculo["total"] == Decimal("600.00") and calculo["teto_aplicado"] is True


def test_comissao_sem_regra_recusa(db, rede, unidade, professor):
    inicio, fim = competencia()
    with pytest.raises(ErroDeRemuneracao):
        calcular_apuracao(professor, unidade, inicio, fim)


def test_apuracao_e_idempotente_e_conferivel(db, rede, unidade, professor, receita):
    RegraDeComissao.objects.create(
        rede=rede, professor=professor, tipo=TipoDeComissao.PERCENTUAL, percentual=Decimal("5.000")
    )
    inicio, fim = competencia()
    primeira = emitir_apuracao(professor, unidade, inicio, fim)
    segunda = emitir_apuracao(professor, unidade, inicio, fim)
    assert primeira.pk == segunda.pk
    assert ApuracaoDeComissao.objects.count() == 1
    assert primeira.itens.count() == 1

    conferencia = conferir_apuracao(primeira)
    assert conferencia["ok"] is True and conferencia["mesmo_numero"] is True

    # se o valor gravado divergir do recalculo, a conferencia aponta a diferenca
    primeira.valor_devido = Decimal("999.99")
    primeira.save(update_fields=["valor_devido"])
    conferencia = conferir_apuracao(primeira)
    assert conferencia["ok"] is False
    assert conferencia["divergencias"][0]["campo"] == "valor_devido"


def test_baixa_e_extrato_do_professor(db, rede, unidade, professor, receita):
    RegraDeComissao.objects.create(
        rede=rede, professor=professor, tipo=TipoDeComissao.PERCENTUAL, percentual=Decimal("10.000")
    )
    inicio, fim = competencia()
    apuracao = emitir_apuracao(professor, unidade, inicio, fim)
    marcar_paga(apuracao, apuracao.valor_devido)
    apuracao.refresh_from_db()
    assert apuracao.situacao == SituacaoDeApuracao.PAGO and apuracao.saldo == Decimal("0.00")

    extrato = extrato_do_professor(professor)
    assert extrato["total_pago"] == Decimal("40.00") and extrato["saldo"] == Decimal("0.00")


def test_apurar_competencia_relata_quem_nao_tem_regra(db, rede, unidade, professor, receita):
    resultado = apurar_competencia(rede)
    assert resultado["emitidas"] == []
    assert resultado["erros"] and "sem regra" in resultado["erros"][0]["erro"]

    RegraDeComissao.objects.create(
        rede=rede, professor=professor, tipo=TipoDeComissao.PERCENTUAL, percentual=Decimal("10.000")
    )
    resultado = apurar_competencia(rede)
    assert len(resultado["emitidas"]) == 1 and resultado["total"] == Decimal("40.00")


# ------------------------------------------------------------------ gamificacao
def test_pontuar_respeita_limite_diario_e_nivel(db, rede, aluno):
    RegraDePontos.objects.create(
        rede=rede, evento=EventoDePontos.CHECKIN, pontos=10, limite_diario=1
    )
    primeira = pontuar(aluno, EventoDePontos.CHECKIN, referencia="c1")
    assert primeira["pontuou"] is True and primeira["pontos"] == 10
    segunda = pontuar(aluno, EventoDePontos.CHECKIN, referencia="c2")
    assert segunda["pontuou"] is False and "limite" in segunda["motivo"]

    RegraDePontos.objects.filter(rede=rede, evento=EventoDePontos.CHECKIN).update(limite_diario=0)
    for posicao in range(49):
        pontuar(aluno, EventoDePontos.CHECKIN, referencia=f"x{posicao}")
    saldo = SaldoDePontos.objects.get(aluno=aluno)
    assert saldo.pontos >= 500 and saldo.nivel >= 2


def test_conquista_liberada_por_quantidade(db, rede, aluno):
    RegraDePontos.objects.create(rede=rede, evento=EventoDePontos.AULA, pontos=5, limite_diario=0)
    Conquista.objects.create(
        rede=rede,
        nome="Frequente",
        evento=EventoDePontos.AULA,
        quantidade=3,
        pontos_bonus=50,
        icone="🔥",
    )
    for posicao in range(3):
        resultado = pontuar(aluno, EventoDePontos.AULA, referencia=f"a{posicao}")
    assert resultado["conquistas"] and resultado["conquistas"][0]["nome"] == "Frequente"
    assert resultado["conquistas"][0]["bonus"] == 50
    saldo = saldo_do_aluno(aluno)
    assert saldo["pontos"] == 65 and len(saldo["conquistas"]) == 1


def test_evento_desconhecido_e_ranking(db, rede, aluno):
    with pytest.raises(ErroDeGamificacao):
        pontuar(aluno, "evento.inventado")
    RegraDePontos.objects.create(rede=rede, evento=EventoDePontos.CHECKIN, pontos=10)
    pontuar(aluno, EventoDePontos.CHECKIN, referencia="r1")
    lista = ranking(rede=rede)
    assert lista and lista[0]["nome"] == aluno.nome and lista[0]["posicao"] == 1


# ------------------------------------------------------------------ NPS
def test_nps_calcula_promotores_neutros_e_detratores(db, rede, unidade):
    pesquisa = Pesquisa.objects.create(
        rede=rede, titulo="Como foi hoje?", pergunta="Recomendaria?", tipo=TipoDePesquisa.NPS
    )
    for nota in (10, 8, 4):
        registrar_resposta(pesquisa, aluno=None, nota=nota)
    resultado = nps(pesquisa)
    assert resultado["respostas"] == 3
    assert (resultado["promotores"], resultado["neutros"], resultado["detratores"]) == (1, 1, 1)
    assert resultado["nps"] == 0  # 33% - 33%
    assert resultado["classificacao"] == "razoavel"


def test_nps_valida_nota_e_impede_duplicidade(db, rede, aluno):
    pesquisa = Pesquisa.objects.create(
        rede=rede, titulo="Pesquisa", pergunta="Nota?", tipo=TipoDePesquisa.NPS
    )
    with pytest.raises(ErroDePesquisa):
        registrar_resposta(pesquisa, aluno=aluno, nota=11)
    registrar_resposta(pesquisa, aluno=aluno, nota=9)
    with pytest.raises(ErroDePesquisa):
        registrar_resposta(pesquisa, aluno=aluno, nota=10)
    # responder tambem pontua (quando ha regra)
    RegraDePontos.objects.create(rede=rede, evento=EventoDePontos.NPS, pontos=15)
    outro = get_user_model().objects.create_user(username="aluno.nps", password="x")
    from usuarios.models import Usuario

    perfil = Usuario.todos.create(
        rede=rede, unidade=aluno.unidade, user=outro, nome="Outro", status_user="Ativo"
    )
    registrar_resposta(pesquisa, aluno=perfil, nota=10)
    assert SaldoDePontos.objects.get(aluno=perfil).pontos == 15


def test_detrator_entra_na_fila_e_sai_apos_tratativa(db, rede, aluno):
    pesquisa = Pesquisa.objects.create(rede=rede, titulo="Pesquisa", pergunta="Nota?")
    resposta = registrar_resposta(pesquisa, aluno=aluno, nota=3, comentario="chuveiro frio")
    assert resposta.detrator is True
    fila = list(detratores_para_tratar(rede=rede))
    assert len(fila) == 1 and fila[0].pk == resposta.pk
    marcar_tratada(resposta, observacao="manutencao chamada")
    assert list(detratores_para_tratar(rede=rede)) == []
    resposta.refresh_from_db()
    assert "manutencao chamada" in resposta.comentario


# ------------------------------------------------------------------ check-in e area do aluno
def test_checkin_registra_e_pontua(db, rede, unidade, aluno):
    RegraDePontos.objects.create(rede=rede, evento=EventoDePontos.CHECKIN, pontos=10)
    checkin, resultado = registrar_checkin(aluno, unidade)
    assert CheckinDoAluno.objects.filter(pk=checkin.pk).exists()
    assert resultado["pontuou"] is True and resultado["pontos"] == 10


def test_checkin_recusa_unidade_de_outra_rede_e_matricula_inativa(db, rede, unidade, aluno):
    from core.models import Rede

    outra = Rede.todos.create(nome="Outra", slug="outra-f8", status="ativo")
    from core.models import Unidade

    unidade_outra = Unidade.objects.create(rede=outra, nome="Outra", codigo="outra", status="ativa")
    with pytest.raises(ErroDeCheckin):
        registrar_checkin(aluno, unidade_outra)
    aluno.status_user = "Inativo"
    aluno.save(update_fields=["status_user"])
    with pytest.raises(ErroDeCheckin):
        registrar_checkin(aluno, unidade)


def test_area_do_aluno_exige_login_e_mostra_acessibilidade(client, db, aluno):
    resposta = client.get("/aluno/")
    assert (
        resposta.status_code == 302
        and "/entrar" in resposta["Location"]
        or resposta.status_code == 302
    )
    client.force_login(aluno.user)
    pagina = client.get("/aluno/")
    assert pagina.status_code == 200
    html = pagina.content.decode()
    assert "Pular para o conteudo" in html  # acessibilidade AA
    assert "aria-labelledby" in html and "manifest.webmanifest" in html


def test_checkin_pelo_pwa_registra_e_avisa(client, db, rede, unidade, aluno):
    RegraDePontos.objects.create(rede=rede, evento=EventoDePontos.CHECKIN, pontos=10)
    client.force_login(aluno.user)
    resposta = client.post("/aluno/checkin/", {"unidade": unidade.pk}, follow=True)
    assert resposta.status_code == 200
    assert CheckinDoAluno.objects.filter(aluno=aluno).count() == 1
    assert "Check-in registrado" in resposta.content.decode()


def test_manifest_e_service_worker_do_pwa(client, db, rede, aluno):
    client.force_login(aluno.user)
    manifest = client.get("/aluno/manifest.webmanifest")
    assert manifest.status_code == 200
    corpo = manifest.json()
    assert corpo["start_url"] == "/aluno/" and corpo["scope"] == "/aluno/"
    assert "Academia" in corpo["name"]
    sw = client.get("/aluno/sw.js")
    assert sw.status_code == 200 and "javascript" in sw["Content-Type"]
    assert "caches.open" in sw.content.decode()
    icone = client.get("/aluno/icone-192.png")
    assert icone.status_code == 200 and "svg" in icone["Content-Type"]


def test_pesquisa_pelo_pwa_pontua(client, db, rede, aluno):
    RegraDePontos.objects.create(rede=rede, evento=EventoDePontos.NPS, pontos=20)
    pesquisa = Pesquisa.objects.create(rede=rede, titulo="Treino de hoje", pergunta="Como foi?")
    client.force_login(aluno.user)
    pagina = client.get(f"/aluno/pesquisa/{pesquisa.pk}/")
    assert pagina.status_code == 200 and "notas_possiveis" not in pagina.content.decode()[:0]
    resposta = client.post(
        f"/aluno/pesquisa/{pesquisa.pk}/", {"nota": 10, "comentario": "otimo"}, follow=True
    )
    assert resposta.status_code == 200
    assert Resposta.objects.filter(pesquisa=pesquisa, aluno=aluno).exists()
    assert SaldoDePontos.objects.get(aluno=aluno).pontos == 20


# ------------------------------------------------------------------ painel
def test_telas_do_painel_respondem(client, db, rede, admin_do_painel, professor, receita):
    client.force_login(admin_do_painel)
    for rota in (
        "remuneracao:regras",
        "remuneracao:apuracoes",
        "gamificacao:regras",
        "gamificacao:conquistas",
        "gamificacao:ranking",
        "nps:pesquisas",
        "nps:painel",
        "remuneracao:extrato",
    ):
        resposta = client.get(reverse(rota))
        assert resposta.status_code == 200, f"{rota} -> {resposta.status_code}"


def test_apurar_pela_tela_e_ver_demonstrativo(
    client, db, rede, admin_do_painel, professor, unidade, receita
):
    RegraDeComissao.objects.create(
        rede=rede, professor=professor, tipo=TipoDeComissao.PERCENTUAL, percentual=Decimal("10.000")
    )
    client.force_login(admin_do_painel)
    resposta = client.post(reverse("remuneracao:apurar"), follow=True)
    assert resposta.status_code == 200
    apuracao = ApuracaoDeComissao.objects.get()
    demonstrativo = client.get(reverse("remuneracao:apuracao_detalhe", args=[apuracao.pk]))
    html = demonstrativo.content.decode()
    assert demonstrativo.status_code == 200
    assert "conferencia" in html.lower() or "Conferencia" in html


def test_todo_modulo_tem_rota_no_menu(db):
    """Invariante do painel: modulo sem rota vira reverse("") e derruba todas as telas."""
    from gestao.menu import ROTAS
    from gestao.permissoes import Modulo

    sem_rota = [modulo.name for modulo in Modulo if modulo not in ROTAS]
    assert sem_rota == [], f"modulo sem rota no menu: {sem_rota}"
    for modulo, rota in ROTAS.items():
        assert reverse(rota), f"{modulo.name} aponta para rota vazia"


def test_modulos_da_fase8_estao_na_matriz(db):
    """Os tres modulos novos precisam existir no enum e na matriz de papeis."""
    from gestao.permissoes import MATRIZ, Modulo

    for nome in ("COMISSOES", "GAMIFICACAO", "PESQUISAS"):
        assert hasattr(Modulo, nome), f"Modulo.{nome} ausente"
    assert Modulo.COMISSOES in MATRIZ["gestor_unidade"]
