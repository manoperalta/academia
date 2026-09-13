"""Dominio proprio, verificacao, certificado e diagnostico (RF-PLT-050..052)."""
from __future__ import annotations

import pytest

from core.models import StatusCertificado, StatusDominio
from governanca.servicos import (
    config_do_router, estado_do_provisionamento, hosts_da_rede, instrucoes_de_dns, rede_por_host,
    reemitir_certificado, subdominio_da, verificar_dominio,
)


class RespostaFalsa:
    def __init__(self, texto, status_code=200):
        self.text = texto
        self.status_code = status_code


def test_sem_dominio_fica_nao_configurado(db, rede):
    resultado = verificar_dominio(rede)
    rede.refresh_from_db()
    assert resultado["ok"] is False
    assert rede.dominio_status == StatusDominio.NAO_CONFIGURADO


def test_verificacao_por_arquivo_no_dominio(db, rede, monkeypatch):
    import governanca.servicos as servicos

    rede.dominio = "academia.exemplo.com.br"
    rede.save()
    token = instrucoes_de_dns(rede)["registros"][1]["valor"]
    monkeypatch.setattr(servicos, "_checar_txt", lambda dominio, valor: (False, "sem dnspython"))
    monkeypatch.setattr(
        servicos, "_checar_arquivo_no_dominio",
        lambda dominio, valor: (True, "token encontrado") if valor in token else (False, "nada"),
    )
    resultado = verificar_dominio(rede, forcar=True)
    rede.refresh_from_db()
    assert resultado["ok"] is True
    assert rede.dominio_status == StatusDominio.PRONTO
    assert rede.dominio_verificado_em is not None
    assert rede.certificado_status == StatusCertificado.EMITINDO


def test_verificacao_sem_arquivo_fica_pendente(db, rede, monkeypatch):
    import governanca.servicos as servicos

    rede.dominio = "academia.exemplo.com.br"
    rede.save()
    monkeypatch.setattr(servicos, "_checar_txt", lambda dominio, valor: (False, "sem TXT"))
    monkeypatch.setattr(servicos, "_checar_arquivo_no_dominio",
                        lambda dominio, valor: (False, "nao encontrei o arquivo de verificacao"))
    resultado = verificar_dominio(rede, forcar=True)
    rede.refresh_from_db()
    assert resultado["ok"] is False
    assert rede.dominio_status == StatusDominio.PENDENTE_DNS
    assert "arquivo" in rede.dominio_diagnostico


def test_instrucoes_de_dns_trazem_a_a_txt_e_cname(db, rede):
    rede.dominio = "academia.exemplo.com.br"
    rede.save()
    instrucoes = instrucoes_de_dns(rede)
    tipos = {registro["tipo"] for registro in instrucoes["registros"]}
    assert tipos == {"A", "TXT", "CNAME"}
    assert instrucoes["arquivo_de_teste"]["conteudo"] == rede.dominio_token


def test_estado_do_provisionamento_em_linguagem_de_cliente(db, rede):
    estado = estado_do_provisionamento(rede)
    assert estado["pronto"] is True  # sem dominio proprio, o subdominio ja basta
    assert any("Endereco do painel" in passo["nome"] for passo in estado["passos"])

    rede.dominio = "academia.exemplo.com.br"
    rede.dominio_status = StatusDominio.PENDENTE_DNS
    rede.dominio_diagnostico = "aguardando propagacao do DNS"
    rede.save()
    estado = estado_do_provisionamento(rede)
    assert estado["pronto"] is False
    assert "propagacao" in estado["passos"][1]["detalhe"]


def test_reemitir_certificado_exige_dominio_pronto(db, rede):
    rede.dominio = "academia.exemplo.com.br"
    rede.dominio_status = StatusDominio.PENDENTE_DNS
    rede.save()
    assert reemitir_certificado(rede)["ok"] is False
    rede.dominio_status = StatusDominio.PRONTO
    rede.save()
    assert reemitir_certificado(rede)["ok"] is True


def test_config_do_router_cobre_os_dois_hosts(db, rede):
    rede.dominio = "academia.exemplo.com.br"
    rede.save()
    config = config_do_router(rede)
    assert subdominio_da(rede) in config and "academia.exemplo.com.br" in config
    assert "certResolver" in config
    assert set(hosts_da_rede(rede)) == {subdominio_da(rede), "academia.exemplo.com.br"}


def test_resolucao_por_host(db, rede):
    assert rede_por_host(subdominio_da(rede)) == rede
    assert rede_por_host("outra.academia.safestack.com.br") is None
    rede.dominio = "academia.exemplo.com.br"
    rede.save()
    assert rede_por_host("academia.exemplo.com.br") == rede
    assert rede_por_host("testserver") is None
