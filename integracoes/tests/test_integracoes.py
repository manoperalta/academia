"""Tela de integracoes: escolher o provedor, ver os campos dele, gravar e espelhar.

Requisito de produto: "deixe tudo preparado para selecionar a integracao e ao selecionar deve
aparecer os campos para preencher com os valores de integracao fornecido pelo terceiro".
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from api.models import RegistroAuditoria
from financeiro.models import GatewayConfig
from fiscal.models import ConfiguracaoFiscal
from integracoes import catalogo, servicos
from integracoes.models import IntegracaoDaRede
from notificacoes.models import ConfiguracaoEmail

pytestmark = pytest.mark.django_db

SENHA_ASAAS = "$aact_chave-secreta-do-asaas"


def _asaas(**extra):
    dados = {"chave_api": SENHA_ASAAS, "ambiente": "sandbox"}
    dados.update(extra)
    return dados


def _postar_asaas(cliente, **extra):
    return cliente.post(reverse("integracoes:configurar", args=["asaas"]), _asaas(**extra))


def test_lista_traz_o_seletor_de_integracoes(cliente_logado):
    resposta = cliente_logado.get(reverse("integracoes:painel"))
    assert resposta.status_code == 200
    conteudo = resposta.content.decode()
    for integracao in catalogo.CATALOGO.values():
        assert integracao.nome.split(" (")[0] in conteudo


def test_ao_escolher_o_provedor_aparecem_so_os_campos_dele(cliente_logado):
    resposta = cliente_logado.get(reverse("integracoes:configurar", args=["asaas"]))
    assert resposta.status_code == 200
    formulario = resposta.context["form"]
    assert list(formulario.fields) == [campo.nome for campo in catalogo.CATALOGO["asaas"].campos]
    assert "senha_do_certificado" not in formulario.fields, "campo de outro provedor nao aparece"
    assert "chave_api" in formulario.fields


def test_seletor_da_lista_leva_para_os_campos_do_provedor(cliente_logado):
    resposta = cliente_logado.get(reverse("integracoes:painel"), {"provedor": "nfse"})
    assert resposta.status_code == 302
    assert resposta["Location"] == reverse("integracoes:configurar", args=["nfse"])


def test_salvar_grava_os_valores_e_espelha_no_gateway(cliente_logado, rede):
    resposta = _postar_asaas(cliente_logado)
    assert resposta.status_code == 302
    registro = IntegracaoDaRede.todos.get(rede=rede, provedor="asaas")
    assert registro.campos["chave_api"] == SENHA_ASAAS
    assert registro.ativo is True

    gateway = GatewayConfig.todos.get(rede=rede)
    assert gateway.gateway == "asaas"
    assert gateway.access_token == SENHA_ASAAS
    assert gateway.ambiente == "sandbox"


def test_segredo_nao_volta_para_a_tela(cliente_logado):
    _postar_asaas(cliente_logado)
    resposta = cliente_logado.get(reverse("integracoes:configurar", args=["asaas"]))
    assert SENHA_ASAAS not in resposta.content.decode(), "a chave nunca volta para o HTML"
    assert resposta.context["form"].fields["chave_api"].required is False


def test_segredo_em_branco_mantem_o_valor_gravado(cliente_logado, rede):
    _postar_asaas(cliente_logado)
    resposta = _postar_asaas(cliente_logado, chave_api="", ambiente="producao")
    assert resposta.status_code == 302
    registro = IntegracaoDaRede.todos.get(rede=rede, provedor="asaas")
    assert registro.campos["chave_api"] == SENHA_ASAAS
    assert registro.campos["ambiente"] == "producao"


def test_campo_obrigatorio_faltando_bloqueia_e_diz_o_que_falta(cliente_logado, rede):
    resposta = _postar_asaas(cliente_logado, chave_api="")
    assert resposta.status_code == 200
    assert "chave_api" in resposta.context["form"].errors
    registro = IntegracaoDaRede.todos.filter(rede=rede, provedor="asaas").first()
    assert registro is None or registro.ativo is False
    pronta, recado = servicos.testar(rede, "asaas")
    assert pronta is False
    assert "Chave da API" in recado


def test_nfse_espelha_na_configuracao_fiscal(cliente_logado, rede):
    cliente_logado.post(
        reverse("integracoes:configurar", args=["nfse"]),
        {
            "provedor": "ginfes",
            "ambiente": "homologacao",
            "token": "token-do-provedor",
            "inscricao_municipal": "123456",
            "municipio": "Montenegro",
            "codigo_do_servico": "6.01",
            "aliquota_iss": "5.00",
            "serie": "1",
        },
    )
    fiscal = ConfiguracaoFiscal.objects.get(rede=rede)
    assert fiscal.provedor == "ginfes"
    assert fiscal.token == "token-do-provedor"
    assert fiscal.municipio == "Montenegro"
    assert fiscal.aliquota_iss == Decimal("5.00")


def test_smtp_espelha_na_configuracao_de_email(cliente_logado, rede):
    cliente_logado.post(
        reverse("integracoes:configurar", args=["smtp"]),
        {
            "host": "smtp.exemplo.com.br",
            "porta": "587",
            "usuario": "academia@exemplo.com.br",
            "senha": "segredo-do-smtp",
            "usar_tls": "on",
            "remetente_email": "academia@exemplo.com.br",
        },
    )
    config = ConfiguracaoEmail.todos.get(rede=rede)
    assert config.host == "smtp.exemplo.com.br"
    assert config.port == 587
    assert config.password == "segredo-do-smtp"
    assert config.use_tls is True


def test_certificado_guarda_arquivo_e_nao_os_bytes_no_json(cliente_logado, rede):
    arquivo = SimpleUploadedFile("certificado.pfx", b"conteudo-do-certificado-a1")
    resposta = cliente_logado.post(
        reverse("integracoes:configurar", args=["certificado_icp"]),
        {
            "arquivo": arquivo,
            "senha_do_certificado": "senha-do-pfx",
            "cnpj": "00.000.000/0000-00",
        },
    )
    assert resposta.status_code == 302
    registro = IntegracaoDaRede.todos.get(rede=rede, provedor="certificado_icp")
    assert registro.arquivo, "o certificado fica no campo de arquivo"
    assert registro.campos["arquivo"].endswith(".pfx")
    assert "conteudo-do-certificado" not in str(registro.campos)


def test_catraca_gera_token_sugerido(cliente_logado):
    resposta = cliente_logado.get(
        reverse("integracoes:configurar", args=["catraca"]), {"gerar_token": "1"}
    )
    assert resposta.status_code == 200
    assert len(resposta.context["form"].fields["token"].initial) >= 20


def test_integracao_de_uma_rede_nao_aparece_na_outra(cliente_logado, rede, outra_rede):
    _postar_asaas(cliente_logado)
    assert servicos.valores_reais(rede, "asaas")
    assert servicos.valores_reais(outra_rede, "asaas") == {}
    assert "Chave da API" in servicos.faltando(outra_rede, "asaas")


def test_alteracao_fica_na_auditoria(cliente_logado):
    _postar_asaas(cliente_logado)
    evento = RegistroAuditoria.objects.filter(acao="alterar", entidade="integracao").first()
    assert evento is not None
    assert "Asaas" in evento.descricao


def test_testar_avisa_o_que_falta_e_depois_confirma(cliente_logado, rede):
    resposta = cliente_logado.post(reverse("integracoes:testar", args=["asaas"]))
    assert resposta.status_code == 302
    pronta, recado = servicos.testar(rede, "asaas")
    assert pronta is False
    assert "Falta preencher" in recado

    _postar_asaas(cliente_logado)
    pronta, recado = servicos.testar(rede, "asaas")
    assert pronta is True
    assert "gravados" in recado


def test_gestor_da_unidade_ve_mas_nao_configura(cliente_gestor):
    assert cliente_gestor.get(reverse("integracoes:painel")).status_code == 200
    resposta = cliente_gestor.post(reverse("integracoes:configurar", args=["asaas"]), _asaas())
    assert resposta.status_code == 403
    assert not IntegracaoDaRede.todos.filter(provedor="asaas").exists()


def test_recepcao_e_professor_nao_entram(cliente_recepcao, cliente_professor):
    assert cliente_recepcao.get(reverse("integracoes:painel")).status_code == 403
    assert cliente_professor.get(reverse("integracoes:painel")).status_code == 403


def test_rota_aparece_no_menu_do_painel(cliente_logado):
    contexto = cliente_logado.get(reverse("gestao:visao_geral")).context
    modulos = [item["modulo"] for item in contexto["menu_painel"]]
    assert "integracoes" in modulos


def test_espelho_existente_nao_e_duplicado(cliente_logado, rede):
    _postar_asaas(cliente_logado)
    _postar_asaas(cliente_logado, ambiente="producao")
    assert IntegracaoDaRede.todos.filter(rede=rede, provedor="asaas").count() == 1
    assert GatewayConfig.todos.filter(rede=rede).count() == 1
