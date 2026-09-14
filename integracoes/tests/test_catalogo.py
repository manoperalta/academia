"""Catalogo das integracoes: cada provedor declara os campos que o terceiro entrega."""

from __future__ import annotations

from integracoes import catalogo

pytestmark = []


def test_catalogo_tem_os_provedores_declarados_como_pendencia():
    esperados = {"asaas", "nfse", "wellhub", "certificado_icp", "catraca", "whatsapp", "smtp"}
    assert esperados <= set(catalogo.CATALOGO)


def test_todo_provedor_tem_nome_resumo_e_campos():
    for chave, integracao in catalogo.CATALOGO.items():
        assert integracao.nome, chave
        assert integracao.resumo, chave
        assert integracao.categoria, chave
        assert integracao.campos, chave
        for campo in integracao.campos:
            assert campo.nome and campo.rotulo, (chave, campo)
            if campo.tipo == catalogo.SELECAO:
                assert campo.opcoes, (chave, campo.nome)


def test_segredo_e_reconhecido_pelo_tipo_senha():
    assert "chave_api" in catalogo.campos_sensiveis("asaas")
    assert "senha_do_certificado" in catalogo.campos_sensiveis("certificado_icp")
    assert "ambiente" not in catalogo.campos_sensiveis("asaas")


def test_campos_obrigatorios_por_provedor():
    obrigatorios = {campo.nome for campo in catalogo.campos_obrigatorios("catraca")}
    assert {"modelo", "identificador_do_equipamento", "token"} <= obrigatorios
    assert "host" not in obrigatorios


def test_agrupamento_por_categoria_cobre_todo_o_catalogo():
    agrupado = catalogo.por_categoria()
    total = sum(len(itens) for itens in agrupado.values())
    assert total == len(catalogo.CATALOGO)
    assert catalogo.PAGAMENTO in agrupado
    assert catalogo.FISCAL in agrupado


def test_provedor_desconhecido_nao_quebra():
    assert catalogo.obter("nao-existe") is None
    assert catalogo.obter("") is None
    assert catalogo.campos_obrigatorios("nao-existe") == ()
