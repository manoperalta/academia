"""Fixtures da governanca (Fase 5)."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from core.models import VinculoUsuario
from core.papeis import Papel

SENHA = "SenhaForteTeste123"


@pytest.fixture(autouse=True)
def cache_limpo():
    """O limite de tentativas vive no cache; sem isso um teste bloqueia o seguinte."""
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def usuario_governanca(db, rede):
    """Dono da academia com senha conhecida e vinculo ativo."""
    usuario = get_user_model().objects.create_user(
        username="dono.governanca",
        password=SENHA,
        email="dono@academia.com.br",
    )
    VinculoUsuario.todos.get_or_create(
        usuario=usuario,
        rede=rede,
        defaults={"papel": Papel.ADMIN_REDE, "ativo": True},
    )
    return usuario


@pytest.fixture
def cliente_governanca(db, usuario_governanca):
    cliente = Client()
    cliente.force_login(usuario_governanca)
    return cliente


@pytest.fixture
def staff_sem_2fa(db):
    usuario = get_user_model().objects.create_user(
        username="equipe.plataforma",
        password=SENHA,
        email="equipe@safestack.com.br",
        is_staff=True,
    )
    cliente = Client()
    cliente.force_login(usuario)
    return cliente, usuario


@pytest.fixture
def arquivo_de_midia(db, rede, tmp_path, settings):
    """Arquivo no namespace do cliente, dentro de um MEDIA_ROOT temporario."""
    settings.MEDIA_ROOT = tmp_path
    pasta = tmp_path / "redes" / rede.slug
    pasta.mkdir(parents=True, exist_ok=True)
    arquivo = pasta / "logo.png"
    arquivo.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 32)
    return arquivo


@pytest.fixture
def aluno_com_login(db, rede):
    """Aluno com usuario de login, ficha de saude e um pagamento (para LGPD)."""
    from decimal import Decimal

    from django.utils import timezone

    from financeiro.models import Pagamento
    from usuarios.models import FichaSaude, Usuario

    login = get_user_model().objects.create_user(
        username="aluno.governanca",
        password=SENHA,
        email="aluno@exemplo.com",
    )
    aluno = Usuario.todos.create(
        rede=rede,
        user=login,
        nome="Ana Aluna",
        email_user="ana@exemplo.com",
        telefone_user="51999990000",
        cpf_cnpj_user="111.444.777-35",
        data_nasc="1990-05-10",
        status_user="Ativo",
    )
    FichaSaude.todos.create(
        rede=rede,
        usuario=aluno,
        peso=Decimal("62.5"),
        altura=Decimal("1.68"),
        restricoes="joelho",
        obs="faz musculacao",
        usa_medicamento=False,
    )

    campos = {campo.name for campo in Pagamento._meta.get_fields()}
    dados = {"rede": rede, "usuario": login}
    if "valor" in campos:
        dados["valor"] = Decimal("150.00")
    if "valor_pago" in campos:
        dados["valor_pago"] = Decimal("150.00")
    if "data_pagamento" in campos:
        dados["data_pagamento"] = timezone.localdate()
    if "data_inicio" in campos:
        dados["data_inicio"] = timezone.localdate()
    if "data_fim" in campos:
        dados["data_fim"] = timezone.localdate() + timedelta(days=30)
    if "status" in campos:
        dados["status"] = "pago"
    if "plano" in campos:
        dados["plano"] = None
    pagamento = Pagamento.objects.create(
        **{chave: valor for chave, valor in dados.items() if valor is not None or chave == "plano"}
    )
    return {"aluno": aluno, "login": login, "pagamento": pagamento}
