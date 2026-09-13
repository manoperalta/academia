"""Recursos da rede: comparativo, metas, governanca, alcadas, onboarding e transferencias."""

from __future__ import annotations

from decimal import Decimal

import pytest

from rede.models import (
    Comunicado,
    ItemDeChecklist,
    LeituraDeComunicado,
    Meta,
    PoliticaDaRede,
    SolicitacaoDeAprovacao,
    TemplateDeUnidade,
    TransferenciaDeAluno,
)
from rede.servicos import (
    ErroDeRede,
    aplicar_template,
    comparativo_entre_unidades,
    consolidado_da_rede,
    distribuir_catalogo,
    encerrar_unidade,
    marcar_item_do_checklist,
    periodo_do_mes,
    transferir_alunos,
    travas_vigentes,
    validar_desconto,
)
from rede.views import pode_criar_unidade


def test_comparativo_ranqueia_por_receita(db, rede, unidades, receita):
    inicio, fim = periodo_do_mes()
    comparativo = comparativo_entre_unidades(rede, inicio, fim)
    assert [linha["posicao"] for linha in comparativo] == [1, 2, 3]
    assert comparativo[0]["recebido"] >= comparativo[-1]["recebido"]
    assert comparativo[0]["alunos_ativos"] >= 3
    assert comparativo[0]["inadimplencia"] > 0  # há pagamento em aberto
    assert comparativo[0]["ticket_medio"] > 0


def test_consolidado_soma_as_unidades(db, rede, unidades, receita):
    inicio, fim = periodo_do_mes()
    consolidado = consolidado_da_rede(rede, inicio, fim)
    assert consolidado["unidades"] == 3
    assert consolidado["recebido"] == sum(linha["recebido"] for linha in consolidado["comparativo"])
    assert consolidado["resultado"] == consolidado["recebido"] - consolidado["despesas"]
    assert consolidado["por_mes"]


def test_metas_calculam_realizado_e_atingimento(db, rede, unidades, receita):
    inicio, fim = periodo_do_mes()
    meta = Meta.objects.create(
        rede=rede,
        unidade=unidades[0],
        inicio=inicio,
        fim=fim,
        indicador=Meta.Indicador.FATURAMENTO,
        alvo=Decimal("300.00"),
    )
    from rede.servicos import atualizar_metas

    atualizar_metas(rede)
    meta.refresh_from_db()
    assert meta.realizado == Decimal("450.00")
    assert meta.atingida is True
    assert meta.atingimento == Decimal("150.00")


def test_politica_trava_desconto_acima_do_teto(db, rede, unidades):
    PoliticaDaRede.objects.create(
        rede=rede, trava_politica_de_desconto=True, teto_de_desconto=Decimal("10.00")
    )
    dentro = validar_desconto(unidades[0], Decimal("8.00"))
    assert dentro["permitido"] is True and dentro["exige_aprovacao"] is False
    fora = validar_desconto(unidades[0], Decimal("25.00"))
    assert fora["permitido"] is False and fora["exige_aprovacao"] is True
    assert "teto" in fora["mensagem"].lower()


def test_travas_vigentes_refletem_a_politica(db, rede):
    PoliticaDaRede.objects.create(rede=rede, trava_planos_e_precos=True, trava_contratos=False)
    travas = travas_vigentes(rede)
    assert travas["planos_e_precos"] is True and travas["contratos"] is False


def test_comunicado_com_leitura_confirmada(db, rede, admin_da_rede):
    comunicado = Comunicado.objects.create(
        rede=rede, titulo="Novo padrão de grade", mensagem="A partir de segunda vale a grade nova."
    )
    LeituraDeComunicado.objects.create(comunicado=comunicado, usuario=admin_da_rede)
    assert comunicado.leituras == 1


def test_alcada_de_aprovacao_registra_decisao(db, rede, unidades, admin_da_rede):
    pedido = SolicitacaoDeAprovacao.objects.create(
        rede=rede,
        unidade=unidades[0],
        tipo=SolicitacaoDeAprovacao.Tipo.DESCONTO_ACIMA_DO_TETO,
        titulo="20% para plano anual",
        valor=Decimal("300.00"),
        solicitante=admin_da_rede,
    )
    pedido.decidir(admin_da_rede, aprovar=False, justificativa="Acima da política")
    pedido.refresh_from_db()
    assert pedido.situacao == SolicitacaoDeAprovacao.Situacao.RECUSADA
    assert pedido.decidido_em is not None


def test_limite_de_unidades_do_pacote(db, rede, unidades):
    from datetime import date

    from plataforma.models import Assinatura, Pacote

    pacote = Pacote.objects.create(
        nome="Bronze",
        codigo="bronze",
        preco_mensal=Decimal("99.00"),
        limite_alunos=150,
        limite_professores=10,
        limite_unidades=2,
        visivel_no_site=True,
    )
    Assinatura.objects.create(
        rede=rede, pacote=pacote, inicio=date(2026, 1, 1), renovacao_em=date(2026, 12, 1)
    )
    permitido, aviso = pode_criar_unidade(rede)
    assert permitido is False
    assert "2 unidade" in aviso and "pacote" in aviso.lower()


def test_transferencia_em_lote_mantem_historico(db, rede, unidades, receita, admin_da_rede):
    alunos = list(
        __import__("usuarios.models", fromlist=["Usuario"]).Usuario.todos.filter(
            rede=rede, unidade=unidades[0]
        )
    )
    resultado = transferir_alunos(
        alunos, unidades[1], motivo="fechamento temporario", usuario=admin_da_rede
    )
    assert resultado["transferidos"] == len(alunos)
    assert resultado["lote"]
    assert TransferenciaDeAluno.objects.filter(lote=resultado["lote"]).count() == len(alunos)
    for aluno in alunos:
        aluno.refresh_from_db()
        assert aluno.unidade == unidades[1]


def test_encerramento_move_alunos_e_inativa(db, rede, unidades, receita, admin_da_rede):
    resultado = encerrar_unidade(unidades[0], unidades[2], usuario=admin_da_rede)
    unidades[0].refresh_from_db()
    assert unidades[0].status == "inativa"
    assert resultado["transferidos"] == resultado["alunos"] > 0
    assert Comunicado.objects.filter(titulo__icontains="encerrada").exists()
    assert (
        not __import__("usuarios.models", fromlist=["Usuario"])
        .Usuario.todos.filter(rede=rede, unidade=unidades[0])
        .exists()
    )


def test_encerramento_recusa_destino_igual(db, rede, unidades):
    with pytest.raises(ErroDeRede):
        encerrar_unidade(unidades[0], unidades[0])


def test_onboarding_aplica_template_e_checklist(db, rede, unidades):
    template = TemplateDeUnidade.objects.create(
        rede=rede,
        nome="Padrao franquia",
        configuracoes={
            "branding": {"sobrescrever": True},
            "planos": ["Mensal"],
            "grades": ["manha"],
            "mensagens": ["boas-vindas"],
        },
    )
    ItemDeChecklist.objects.create(template=template, titulo="Cadastrar CNPJ", ordem=1)
    ItemDeChecklist.objects.create(template=template, titulo="Treinar equipe", ordem=2)
    implantacao = aplicar_template(unidades[0], template)
    unidades[0].refresh_from_db()
    assert unidades[0].sobrescrever_branding is True
    assert "planos" in implantacao.resultado["aplicado"]
    assert implantacao.progresso == 0
    marcar_item_do_checklist(implantacao, template.itens.first().pk)
    implantacao.refresh_from_db()
    assert implantacao.progresso == 50
    for item in template.itens.all():
        marcar_item_do_checklist(implantacao, item.pk)
    implantacao.refresh_from_db()
    assert implantacao.progresso == 100 and implantacao.concluida_em is not None


def test_distribuicao_de_catalogo_para_unidades(db, rede, unidades, admin_da_rede):
    from aulas.models import Aulas as Aula
    from tests.apoio import criar

    aula = criar(Aula, rede=rede, unidade=None)
    distribuicao = distribuir_catalogo(rede, str(aula.pk), unidades, usuario=admin_da_rede)
    assert len(distribuicao.resultado["copias"]) == 3
    assert Aula.todos.filter(rede=rede, unidade__in=unidades).count() == 3


def test_importacao_multi_unidade_confere_e_importa(db, rede, unidades):
    from gestao.importacao import analisar_aplicar_multiunidade

    conteudo = (
        b"nome,email,unidade\n"
        b"Ana Aluna,ana@x.com,Centro\n"
        b"Bruno Aluno,bruno@x.com,Zona Sul\n"
        b"Carla Sem Unidade,carla@x.com,Inexistente\n"
    )
    conferencia = analisar_aplicar_multiunidade(conteudo, rede, dry_run=True)
    assert conferencia["criados"] == 2
    assert any(
        "nao encontrada" in erro
        for dados in conferencia["por_unidade"].values()
        for erro in dados["erros"]
    )
    from usuarios.models import Usuario

    assert Usuario.todos.filter(rede=rede).count() == 0  # dry-run nao grava

    importacao = analisar_aplicar_multiunidade(conteudo, rede)
    assert importacao["ok"] is True and importacao["criados"] == 2
    assert Usuario.todos.filter(rede=rede, unidade=unidades[0], nome="Ana Aluna").exists()


def test_importacao_sem_coluna_unidade_recusa(db, rede):
    from gestao.importacao import analisar_aplicar_multiunidade

    conteudo = b"nome,email\nAna,ana@x.com\n"
    resultado = analisar_aplicar_multiunidade(conteudo, rede)
    assert resultado["ok"] is False
    assert "unidade" in resultado["mensagem"]
