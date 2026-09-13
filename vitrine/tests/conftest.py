"""Fixtures do site publico e do cadastro self-service."""
from __future__ import annotations

import pytest

from plataforma.tests.conftest import criar_pacote


def cnpj_valido(base: str = "11222333", ordem: str = "0001") -> str:
    """Gera um CNPJ valido (digitos verificadores calculados) para os testes."""
    pesos = ([5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2], [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])

    def digito(parcial: str, pesos_do_digito) -> str:
        soma = sum(int(numero) * peso for numero, peso in zip(parcial, pesos_do_digito, strict=True))
        resto = soma % 11
        return "0" if resto < 2 else str(11 - resto)

    parcial = base + ordem
    primeiro = digito(parcial, pesos[0])
    return parcial + primeiro + digito(parcial + primeiro, pesos[1])


@pytest.fixture
def pacotes_publicos(db):
    prata = criar_pacote("prata", "Prata", 100, 5, 1, "125.00", ["impressao_pdf"])
    bronze = criar_pacote("bronze", "Bronze", 150, 10, 1, "99.00",
                          ["whatsapp", "relatorios_avancados"])
    ouro = criar_pacote("ouro", "Ouro", None, None, None, "199.00",
                        ["whatsapp", "relatorios_avancados", "api", "multi_unidade"])
    return {"prata": prata, "bronze": bronze, "ouro": ouro}


@pytest.fixture
def dados_cadastro():
    return {
        "nome": "Academia Nova Forca",
        "cnpj": cnpj_valido(),
        "responsavel": "Jonathan Teste",
        "email": "dono@academiaforca.com.br",
        "telefone": "51999998888",
        "slug": "academia-forca",
        "modalidade": "trial",
        "aceite": "on",
    }
