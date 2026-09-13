"""Convites de equipe: criacao, envio, aceite e ciclo de vida."""

from __future__ import annotations

from django.core import mail
from django.urls import reverse
from django.utils import timezone

from core.models import ConviteEquipe, VinculoUsuario
from core.papeis import Papel


def _convidar(cliente, email="novo@exemplo.com", papel="recepcao", unidade=""):
    return cliente.post(
        reverse("gestao:convite_novo"),
        {"email": email, "papel": papel, "unidade": unidade},
    )


def test_convidar_gera_token_expira_e_envia_email(cliente_logado, rede):
    resposta = _convidar(cliente_logado)
    assert resposta.status_code == 302
    convite = ConviteEquipe.objects.get(email="novo@exemplo.com")
    assert convite.rede_id == rede.pk
    assert convite.status == ConviteEquipe.Status.PENDENTE
    assert len(convite.token) >= 16
    assert convite.expirado is False
    assert convite.esta_valido() is True
    assert len(mail.outbox) == 1
    assert "convite" in mail.outbox[0].subject.lower()
    assert convite.token in mail.outbox[0].body


def test_convite_nao_pode_ser_para_aluno(cliente_logado):
    resposta = _convidar(cliente_logado, papel="aluno")
    assert resposta.status_code == 200
    assert not ConviteEquipe.objects.exists()


def test_aceitar_convite_cria_conta_e_vinculo(client, cliente_logado):
    _convidar(cliente_logado, email="recepcao.nova@exemplo.com", papel="recepcao")
    convite = ConviteEquipe.objects.get(email="recepcao.nova@exemplo.com")
    resposta = client.post(
        reverse("gestao:convite_aceitar", args=[convite.token]),
        {"nome": "Nova Pessoa", "senha": "SenhaMuitoForte1", "senha2": "SenhaMuitoForte1"},
    )
    assert resposta.status_code == 302
    convite.refresh_from_db()
    assert convite.status == ConviteEquipe.Status.ACEITO
    assert convite.aceito_por is not None
    vinculo = VinculoUsuario.todos.get(usuario=convite.aceito_por)
    assert vinculo.rede_id == convite.rede_id
    assert vinculo.papel == Papel.RECEPCAO
    assert vinculo.ativo is True
    # a pessoa ja entra logada e consegue abrir o painel
    assert client.get(reverse("gestao:visao_geral")).status_code == 200


def test_convite_expirado_nao_cria_vinculo(client, cliente_logado):
    _convidar(cliente_logado, email="atrasado@exemplo.com")
    convite = ConviteEquipe.objects.get(email="atrasado@exemplo.com")
    convite.expira_em = timezone.now() - timezone.timedelta(days=1)
    convite.save(update_fields=["expira_em"])
    resposta = client.post(
        reverse("gestao:convite_aceitar", args=[convite.token]),
        {"nome": "Atrasado", "senha": "SenhaMuitoForte1", "senha2": "SenhaMuitoForte1"},
    )
    assert resposta.status_code == 200
    convite.refresh_from_db()
    assert convite.status == ConviteEquipe.Status.PENDENTE
    assert not VinculoUsuario.todos.filter(usuario__first_name="Atrasado").exists()


def test_cancelar_convite(cliente_logado):
    _convidar(cliente_logado, email="cancelar@exemplo.com")
    convite = ConviteEquipe.objects.get(email="cancelar@exemplo.com")
    cliente_logado.post(reverse("gestao:convite_cancelar", args=[convite.pk]))
    convite.refresh_from_db()
    assert convite.status == ConviteEquipe.Status.CANCELADO


def test_alternar_acesso_da_equipe(cliente_logado, recepcionista):
    vinculo = VinculoUsuario.todos.get(usuario=recepcionista)
    cliente_logado.post(reverse("gestao:vinculo_alternar", args=[vinculo.pk]))
    vinculo.refresh_from_db()
    assert vinculo.ativo is False
    cliente_logado.post(reverse("gestao:vinculo_alternar", args=[vinculo.pk]))
    vinculo.refresh_from_db()
    assert vinculo.ativo is True


def test_nao_desativa_o_proprio_acesso(cliente_logado, usuario, vinculo_admin):
    cliente_logado.post(reverse("gestao:vinculo_alternar", args=[vinculo_admin.pk]))
    vinculo_admin.refresh_from_db()
    assert vinculo_admin.ativo is True
