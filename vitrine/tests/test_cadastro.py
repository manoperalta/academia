"""Cadastro self-service: provisionamento, trial, pagamento e recusas."""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.urls import reverse
from django.utils import timezone

from academia.models import Configuracao, IdentidadeVisual
from core.models import ConviteEquipe, Rede, VinculoUsuario
from plataforma.models import Assinatura, Fatura, StatusFatura
from plataforma.servicos import slug_disponivel
from plataforma.validadores import normalizar_cnpj, sugerir_slug, validar_cnpj
from vitrine.tests.conftest import cnpj_valido


def _post(client, pacote, dados, **extras):
    corpo = {**dados, "pacote": pacote.codigo, **extras}
    return client.post(reverse("vitrine:cadastro"), corpo)


def test_cadastro_trial_provisiona_a_academia(client, pacotes_publicos, dados_cadastro):
    resposta = _post(client, pacotes_publicos["prata"], dados_cadastro)
    assert resposta.status_code == 302
    assert resposta.url == reverse("vitrine:cadastro_concluido")

    rede = Rede.todos.get(slug="academia-forca")
    assert rede.status == "trial"
    assert rede.trial_termina_em is not None
    assert rede.cnpj == normalizar_cnpj(dados_cadastro["cnpj"])

    assinatura = Assinatura.objects.get(rede=rede)
    assert assinatura.pacote.codigo == "prata"
    assert assinatura.em_trial is True
    assert assinatura.renovacao_em > timezone.localdate()

    assert Configuracao.todos.filter(rede=rede).exists()
    assert IdentidadeVisual.todos.filter(rede=rede).exists()

    dono = get_user_model().objects.get(email=dados_cadastro["email"])
    assert dono.has_usable_password() is False  # senha definida pelo proprio cliente
    vinculo = VinculoUsuario.todos.get(usuario=dono, rede=rede)
    assert vinculo.papel == "admin_rede"

    convite = ConviteEquipe.objects.get(rede=rede)
    assert convite.email == dados_cadastro["email"]
    assert convite.esta_valido() is True

    assert len(mail.outbox) == 1
    assert convite.token in mail.outbox[0].body
    assert "Academia Nova Forca" in mail.outbox[0].subject


def test_cadastro_com_pagamento_gera_fatura_pix(client, pacotes_publicos, dados_cadastro):
    resposta = _post(client, pacotes_publicos["ouro"], dados_cadastro, modalidade="pagamento")
    assert resposta.status_code == 302
    rede = Rede.todos.get(slug="academia-forca")
    assert rede.status == "ativo"
    fatura = Fatura.objects.get(rede=rede)
    assert fatura.status == StatusFatura.ABERTA
    assert Decimal(str(fatura.valor_final)) == Decimal(str(pacotes_publicos["ouro"].preco_mensal))
    assert fatura.pix_copia_cola
    assert fatura.gateway == "simulado"
    assert len(mail.outbox) == 1


def test_slug_duplicado_e_recusado(client, pacotes_publicos, dados_cadastro, rede):
    resposta = _post(client, pacotes_publicos["prata"], {**dados_cadastro, "slug": rede.slug})
    assert resposta.status_code == 200
    assert Rede.todos.filter(slug=rede.slug).count() == 1


def test_slug_reservado_e_recusado(client, pacotes_publicos, dados_cadastro):
    resposta = _post(client, pacotes_publicos["prata"], {**dados_cadastro, "slug": "gestao"})
    assert resposta.status_code == 200
    assert not Rede.todos.filter(slug="gestao").exists()


def test_cnpj_invalido_e_recusado(client, pacotes_publicos, dados_cadastro):
    resposta = _post(
        client, pacotes_publicos["prata"], {**dados_cadastro, "cnpj": "11.111.111/1111-11"}
    )
    assert resposta.status_code == 200
    assert not Rede.todos.filter(slug="academia-forca").exists()


def test_cnpj_repetido_e_recusado(client, pacotes_publicos, dados_cadastro):
    primeiro = _post(client, pacotes_publicos["prata"], dados_cadastro)
    assert primeiro.status_code == 302
    segundo = _post(
        client,
        pacotes_publicos["bronze"],
        {**dados_cadastro, "slug": "outra-academia", "email": "outro@exemplo.com"},
    )
    assert segundo.status_code == 200
    assert not Rede.todos.filter(slug="outra-academia").exists()


def test_aceite_obrigatorio(client, pacotes_publicos, dados_cadastro):
    resposta = _post(client, pacotes_publicos["prata"], {**dados_cadastro, "aceite": ""})
    assert resposta.status_code == 200
    assert not Rede.todos.filter(slug="academia-forca").exists()


def test_provisionamento_e_transacional(client, pacotes_publicos, dados_cadastro, monkeypatch):
    """Falha no meio do caminho nao pode deixar tenant pela metade (RF-PLT-031)."""
    import plataforma.servicos as servicos

    def explode(*args, **kwargs):
        raise RuntimeError("falha simulada no meio do provisionamento")

    monkeypatch.setattr(servicos, "_criar_configuracoes_padrao", explode)
    with pytest.raises(RuntimeError):
        servicos.cadastrar_tenant_publico(
            nome=dados_cadastro["nome"],
            slug=dados_cadastro["slug"],
            cnpj=dados_cadastro["cnpj"],
            responsavel=dados_cadastro["responsavel"],
            email=dados_cadastro["email"],
            telefone=dados_cadastro["telefone"],
            pacote=pacotes_publicos["prata"],
            modalidade="trial",
        )
    assert not Rede.todos.filter(slug=dados_cadastro["slug"]).exists()
    assert not Assinatura.objects.exists()
    assert not get_user_model().objects.filter(email=dados_cadastro["email"]).exists()


def test_conclusao_mostra_link_de_primeiro_acesso(client, pacotes_publicos, dados_cadastro):
    criacao = _post(client, pacotes_publicos["prata"], dados_cadastro)
    assert criacao.status_code == 302, criacao.context.get("form").errors if criacao.context else ""
    resposta = client.get(reverse("vitrine:cadastro_concluido"))
    assert resposta.status_code == 200
    conteudo = resposta.content.decode()
    assert "Academia Nova Forca" in conteudo
    assert "convite/" in conteudo


def test_cnpj_alfanumerico_valido(db):
    """CNPJ alfanumerico (2026): mesma regra, com letras valendo ASCII-48."""

    def dv(parcial, pesos):
        soma = sum(
            (int(c) if c.isdigit() else ord(c) - 48) * w
            for c, w in zip(parcial, pesos, strict=True)
        )
        resto = soma % 11
        return "0" if resto < 2 else str(11 - resto)

    pesos = ([5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2], [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    base = "12ABC3450001"
    primeiro = dv(base, pesos[0])
    alfanumerico = base + primeiro + dv(base + primeiro, pesos[1])
    assert validar_cnpj(alfanumerico) is True
    assert validar_cnpj(alfanumerico[:-1] + ("9" if alfanumerico[-1] != "9" else "8")) is False
    assert validar_cnpj(cnpj_valido()) is True
    assert validar_cnpj("11.222.333/0001-00") is False


def test_validar_cnpj_rejeita_sequencia_repetida(db):
    assert validar_cnpj("11111111111111") is False
    assert validar_cnpj("") is False
    assert validar_cnpj("123") is False


def test_sugerir_slug_e_slug_disponivel(db):
    assert sugerir_slug("Academia Força & Saúde") == "academia-forca-saude"
    assert sugerir_slug("") == "academia"
    assert slug_disponivel("minha-academia")[0] is True
    assert slug_disponivel("ab")[0] is False
    assert slug_disponivel("api")[0] is False
