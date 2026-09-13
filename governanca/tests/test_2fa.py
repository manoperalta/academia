"""Segundo fator: ativacao, desafio, codigos de recuperacao e obrigatoriedade."""

from __future__ import annotations

from django.urls import reverse

from core import totp
from core.seguranca import (
    confirmar_2fa,
    desativar_2fa,
    dois_fatores_ativo,
    gerar_codigos_de_recuperacao,
    iniciar_2fa,
    validar_segundo_fator,
)
from governanca.models import CodigoRecuperacao, Dispositivo2FA


def test_ativar_e_validar(db, usuario_governanca):
    dispositivo = iniciar_2fa(usuario_governanca)
    assert dois_fatores_ativo(usuario_governanca) is False
    assert confirmar_2fa(usuario_governanca, "000000") is False
    codigo = totp.codigo_atual(dispositivo.segredo)
    assert confirmar_2fa(usuario_governanca, codigo) is True
    assert dois_fatores_ativo(usuario_governanca) is True


def test_codigos_de_recuperacao_uso_unico(db, usuario_governanca):
    iniciar_2fa(usuario_governanca)
    confirmar_2fa(
        usuario_governanca,
        totp.codigo_atual(Dispositivo2FA.objects.get(usuario=usuario_governanca).segredo),
    )
    codigos = gerar_codigos_de_recuperacao(usuario_governanca)
    assert len(codigos) == 8
    assert CodigoRecuperacao.objects.filter(usuario=usuario_governanca).count() == 8
    assert validar_segundo_fator(usuario_governanca, codigos[0]) is True
    assert validar_segundo_fator(usuario_governanca, codigos[0]) is False  # uso unico
    assert validar_segundo_fator(usuario_governanca, codigos[1]) is True
    assert validar_segundo_fator(usuario_governanca, "AAAA-BBBB") is False
    usados = CodigoRecuperacao.objects.filter(usuario=usuario_governanca, usado_em__isnull=False)
    assert usados.count() == 2
    assert codigos[0] not in usados.values_list("hash_codigo", flat=True)  # so o hash


def test_desativar_remove_dispositivo_e_codigos(db, usuario_governanca):
    iniciar_2fa(usuario_governanca)
    confirmar_2fa(
        usuario_governanca,
        totp.codigo_atual(Dispositivo2FA.objects.get(usuario=usuario_governanca).segredo),
    )
    gerar_codigos_de_recuperacao(usuario_governanca)
    desativar_2fa(usuario_governanca)
    assert Dispositivo2FA.objects.filter(usuario=usuario_governanca).count() == 0
    assert CodigoRecuperacao.objects.filter(usuario=usuario_governanca).count() == 0
    assert dois_fatores_ativo(usuario_governanca) is False


def test_desafio_bloqueia_painel_ate_confirmar(cliente_governanca, usuario_governanca):
    iniciar_2fa(usuario_governanca)
    confirmar_2fa(
        usuario_governanca,
        totp.codigo_atual(Dispositivo2FA.objects.get(usuario=usuario_governanca).segredo),
    )
    resposta = cliente_governanca.get(reverse("gestao:visao_geral"))
    assert resposta.status_code == 302
    assert reverse("governanca:dois_fatores") in resposta.url

    # a propria pagina do desafio abre
    assert cliente_governanca.get(reverse("governanca:dois_fatores")).status_code == 200
    # codigo errado nao passa
    errado = cliente_governanca.post(reverse("governanca:dois_fatores"), {"codigo": "000000"})
    assert errado.status_code == 200 and "invalido" in errado.content.decode().lower()
    # codigo certo libera e a sessao fica marcada
    certo = cliente_governanca.post(
        reverse("governanca:dois_fatores"),
        {
            "codigo": totp.codigo_atual(
                Dispositivo2FA.objects.get(usuario=usuario_governanca).segredo
            ),
        },
    )
    assert certo.status_code == 302
    assert cliente_governanca.get(reverse("gestao:visao_geral")).status_code == 200


def test_equipe_da_plataforma_e_obrigada_a_ativar(staff_sem_2fa):
    cliente, _usuario = staff_sem_2fa
    resposta = cliente.get(reverse("plataforma:metricas"))
    assert resposta.status_code == 302
    assert reverse("governanca:dois_fatores_cadastrar") in resposta.url


def test_ativacao_pelo_painel_entrega_codigos(cliente_governanca, usuario_governanca):
    pagina = cliente_governanca.get(reverse("governanca:dois_fatores_cadastrar"))
    assert pagina.status_code == 200
    segredo = Dispositivo2FA.objects.get(usuario=usuario_governanca).segredo
    resposta = cliente_governanca.post(
        reverse("governanca:dois_fatores_cadastrar"), {"codigo": totp.codigo_atual(segredo)}
    )
    assert resposta.status_code == 200
    assert "recuperação" in resposta.content.decode().lower()
    assert CodigoRecuperacao.objects.filter(usuario=usuario_governanca).count() == 8


def test_dono_sem_2fa_nao_e_incomodado(cliente_governanca):
    assert cliente_governanca.get(reverse("gestao:visao_geral")).status_code == 200
