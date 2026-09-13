"""Convites de equipe: criacao, envio, aceite e ciclo de vida.

Cobre tambem o caso pedido de produto: ``Admin da rede`` e ``Gestor da unidade``
sendo a mesma pessoa (um convite, dois papeis, dois vinculos com escopos
diferentes) e a uniao de papeis no RBAC.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core import mail
from django.urls import reverse
from django.utils import timezone

from core.models import ConviteEquipe, VinculoUsuario
from core.papeis import Papel
from gestao.permissoes import Modulo, nivel, pode, pode_editar


def _convidar(cliente, email="novo@exemplo.com", papel="recepcao", unidade="", papeis=None):
    return cliente.post(
        reverse("gestao:convite_novo"),
        {
            "email": email,
            "papeis": [papel] if papeis is None else papeis,
            "unidade": unidade,
        },
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
    resposta = _convidar(cliente_logado, papeis=["aluno"])
    assert resposta.status_code == 200
    assert not ConviteEquipe.objects.exists()


def test_convite_sem_papel_e_recusado(cliente_logado):
    resposta = _convidar(cliente_logado, papeis=[])
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


def test_convite_de_dois_papeis_cria_dois_vinculos(client, cliente_logado, rede, unidade):
    """O mesmo CPF pode ser admin da rede e gestor da unidade (pedido de produto)."""
    _convidar(
        cliente_logado,
        email="dono.e.gestor@exemplo.com",
        papeis=[Papel.ADMIN_REDE, Papel.GESTOR_UNIDADE],
        unidade=str(unidade.pk),
    )
    convite = ConviteEquipe.objects.get(email="dono.e.gestor@exemplo.com")
    assert convite.lista_de_papeis() == [Papel.ADMIN_REDE, Papel.GESTOR_UNIDADE]
    assert convite.papel == Papel.ADMIN_REDE  # papel principal, por compatibilidade

    client.post(
        reverse("gestao:convite_aceitar", args=[convite.token]),
        {"nome": "Dono e Gestor", "senha": "SenhaMuitoForte1", "senha2": "SenhaMuitoForte1"},
    )
    convite.refresh_from_db()
    pessoa = convite.aceito_por
    vinculos = VinculoUsuario.todos.filter(usuario=pessoa).order_by("papel")
    assert vinculos.count() == 2

    admin = vinculos.get(papel=Papel.ADMIN_REDE)
    assert admin.unidade_id is None, "papel de rede vale para a rede inteira"
    assert admin.cobre_a_rede() is True

    gestor = vinculos.get(papel=Papel.GESTOR_UNIDADE)
    assert gestor.unidade_id == unidade.pk, "papel de unidade fica na unidade escolhida"

    # e o RBAC soma os dois papeis (rede + unidade)
    assert nivel(pessoa, Modulo.UNIDADES, rede=rede) >= 2
    assert pode_editar(pessoa, Modulo.EQUIPE, rede=rede) is True


def test_uniao_de_papeis_no_rbac(db, rede, unidade):
    """Dois vinculos no mesmo usuario dao a uniao das permissoes, nao a interseccao."""
    pessoa = get_user_model().objects.create_user(
        username="acumula.papeis", password="senha-de-teste-123"
    )
    VinculoUsuario.todos.create(usuario=pessoa, rede=rede, unidade=unidade, papel=Papel.RECEPCAO)
    VinculoUsuario.todos.create(usuario=pessoa, rede=rede, unidade=unidade, papel=Papel.PROFESSOR)

    # so a recepcao ve financeiro; so o professor edita aulas
    assert pode(pessoa, Modulo.FINANCEIRO, rede=rede) is True
    assert pode_editar(pessoa, Modulo.AULAS, rede=rede) is True
    # e nenhum dos dois da acesso a repasses (isso e da rede/admin)
    assert pode(pessoa, Modulo.REPASSES, rede=rede) is False


def test_rotulos_dos_papeis_para_exibicao(db, rede, unidade):
    convite = ConviteEquipe.objects.create(
        rede=rede,
        unidade=unidade,
        email="rotulo@exemplo.com",
        papel=Papel.ADMIN_REDE,
        papeis=[Papel.ADMIN_REDE, Papel.GESTOR_UNIDADE],
        token=ConviteEquipe.gerar_token(),
        expira_em=timezone.now() + timezone.timedelta(days=7),
    )
    assert convite.rotulos_dos_papeis() == "Administrador da rede + Gestor de unidade"

    # convite antigo (sem a lista) continua funcionando
    antigo = ConviteEquipe.objects.create(
        rede=rede,
        email="antigo@exemplo.com",
        papel=Papel.RECEPCAO,
        papeis=[],
        token=ConviteEquipe.gerar_token(),
        expira_em=timezone.now() + timezone.timedelta(days=7),
    )
    assert antigo.lista_de_papeis() == [Papel.RECEPCAO]
    assert antigo.rotulos_dos_papeis() == "Recepcao"


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
