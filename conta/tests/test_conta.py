"""Testes de perfil, senha, sessoes ativas e suporte."""

from __future__ import annotations

import pytest
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from conta import servicos
from conta.models import ChamadoDeSuporte, MensagemDoChamado
from conta.servicos import ErroDeConta

SENHA = "SenhaForteConta!23"
pytestmark = pytest.mark.django_db


# ------------------------------------------------------------------ perfil e senha


def test_aluno_atualiza_o_proprio_perfil(cliente_aluno, aluno):
    resposta = cliente_aluno.post(
        reverse("conta:perfil"),
        {"nome": "Aluna Renomeada", "email": "nova@exemplo.com", "telefone": "51 99999-0000"},
    )
    assert resposta.status_code == 302
    aluno.refresh_from_db()
    aluno.user.refresh_from_db()
    assert aluno.nome == "Aluna Renomeada"
    assert aluno.telefone_user == "51 99999-0000"
    assert aluno.user.email == "nova@exemplo.com"


def test_equipe_sem_perfil_atualiza_so_o_login(cliente_equipe, admin_do_painel):
    cliente_equipe.post(
        reverse("conta:perfil"),
        {"nome": "Nao importa", "email": "equipe@exemplo.com", "telefone": "51"},
    )
    admin_do_painel.refresh_from_db()
    assert admin_do_painel.email == "equipe@exemplo.com"


def test_alterar_senha_e_entrar_com_a_nova(client, aluno):
    client.force_login(aluno.user)
    resposta = client.post(
        reverse("conta:senha"),
        {
            "old_password": SENHA,
            "new_password1": "OutraSenhaForte!45",
            "new_password2": "OutraSenhaForte!45",
        },
    )
    assert resposta.status_code == 302
    assert client.login(username=aluno.user.username, password="OutraSenhaForte!45") is True


def test_senha_atual_errada_nao_altera(client, aluno):
    client.force_login(aluno.user)
    resposta = client.post(
        reverse("conta:senha"),
        {
            "old_password": "errada",
            "new_password1": "OutraSenhaForte!45",
            "new_password2": "OutraSenhaForte!45",
        },
    )
    assert resposta.status_code == 200
    aluno.user.refresh_from_db()
    assert aluno.user.check_password(SENHA) is True


def test_pedir_redefinicao_envia_email_sem_revelar_se_existe(client, aluno):
    resposta = client.post(reverse("conta:senha_redefinir"), {"email": aluno.user.email})
    assert resposta.status_code == 302
    assert len(mail.outbox) == 1
    assert "senha" in mail.outbox[0].subject.lower()

    mail.outbox.clear()
    cliente = client.__class__()
    resposta = cliente.post(reverse("conta:senha_redefinir"), {"email": "naoexiste@exemplo.com"})
    assert resposta.status_code == 302
    assert len(mail.outbox) == 0, "a resposta nao pode revelar se o e-mail existe"


def test_link_de_redefinicao_valido_abre_o_formulario(client, aluno):
    identificador = urlsafe_base64_encode(force_bytes(aluno.user.pk))
    token = default_token_generator.make_token(aluno.user)
    resposta = client.get(
        reverse("conta:senha_confirmar", kwargs={"uidb64": identificador, "token": token})
    )
    # o Django redireciona para a URL de "definir senha" no primeiro acesso ao link
    assert resposta.status_code == 302
    destino = resposta["Location"]
    seguir = client.get(destino)
    assert seguir.status_code == 200
    assert "nova senha" in seguir.content.decode().lower()


# ------------------------------------------------------------------ sessoes


def test_sessoes_mostram_a_atual_e_encerram_as_outras(client, aluno):
    from django.test import Client

    outro = Client()
    assert outro.login(username=aluno.user.username, password=SENHA) is True
    client.force_login(aluno.user)

    lista = client.get(reverse("conta:sessoes")).content.decode()
    assert "este aparelho" in lista
    assert servicos.sessoes_ativas(aluno.user) != []

    chave_atual = client.session.session_key  # depois da requisicao a sessao tem chave
    removidas = servicos.encerrar_outras_sessoes(aluno.user, chave_atual)
    assert removidas >= 1
    restantes = servicos.sessoes_ativas(aluno.user, chave_atual)
    assert restantes and all(sessao["atual"] for sessao in restantes)


# ------------------------------------------------------------------ suporte


def test_abrir_chamado_exige_titulo_e_descricao(rede, admin_do_painel):
    with pytest.raises(ErroDeConta):
        servicos.abrir_chamado(rede=rede, titulo="  ", descricao="algo", aberto_por=admin_do_painel)
    with pytest.raises(ErroDeConta):
        servicos.abrir_chamado(rede=rede, titulo="Erro", descricao="  ", aberto_por=admin_do_painel)


def test_responder_avanca_para_em_andamento(rede, admin_do_painel):
    chamado = servicos.abrir_chamado(
        rede=rede,
        titulo="Catraca travando",
        descricao="A catraca da entrada trava",
        aberto_por=admin_do_painel,
    )
    assert chamado.situacao == ChamadoDeSuporte.Situacao.ABERTO
    servicos.responder(chamado=chamado, texto="Verificando o equipamento", autor=admin_do_painel)
    chamado.refresh_from_db()
    assert chamado.situacao == ChamadoDeSuporte.Situacao.EM_ANDAMENTO
    assert chamado.responsavel == admin_do_painel
    assert MensagemDoChamado.objects.filter(chamado=chamado).count() == 1


def test_chamado_fechado_nao_recebe_resposta(rede, admin_do_painel):
    chamado = servicos.abrir_chamado(
        rede=rede, titulo="Erro", descricao="Detalhe", aberto_por=admin_do_painel
    )
    servicos.mudar_situacao(chamado=chamado, situacao="fechado", responsavel=admin_do_painel)
    with pytest.raises(ErroDeConta):
        servicos.responder(chamado=chamado, texto="mais uma", autor=admin_do_painel)


def test_resolvido_guarda_o_momento_e_sai_da_fila(rede, admin_do_painel):
    chamado = servicos.abrir_chamado(
        rede=rede,
        titulo="Duvida",
        descricao="Como emito nota?",
        prioridade="urgente",
        aberto_por=admin_do_painel,
    )
    assert servicos.fila_do_suporte(rede).count() == 1
    servicos.mudar_situacao(chamado=chamado, situacao="resolvido", responsavel=admin_do_painel)
    chamado.refresh_from_db()
    assert chamado.resolvido_em is not None
    assert servicos.fila_do_suporte(rede).count() == 0
    resumo = servicos.resumo_do_suporte(rede)
    assert resumo["resolvidos"] == 1 and resumo["abertos"] == 0
    assert resumo["horas_medias"] is not None


def test_chamado_de_outra_rede_nao_entra_na_fila(rede, outra_rede, admin_do_painel):
    servicos.abrir_chamado(rede=outra_rede, titulo="Da outra rede", descricao="detalhe")
    assert servicos.fila_do_suporte(rede).count() == 0


# ------------------------------------------------------------------ telas


def test_telas_de_conta_abrem(cliente_aluno):
    for rota in ("conta:perfil", "conta:senha", "conta:sessoes", "conta:chamados"):
        assert cliente_aluno.get(reverse(rota)).status_code == 200, rota


def test_abrir_chamado_pelas_telas(cliente_aluno, aluno):
    resposta = cliente_aluno.post(
        reverse("conta:chamados"),
        {
            "titulo": "App do aluno travando",
            "descricao": "A tela de treino não abre",
            "categoria": "tecnico",
            "prioridade": "alta",
        },
    )
    assert resposta.status_code == 302
    chamado = ChamadoDeSuporte.objects.get()
    assert chamado.aberto_por == aluno.user and chamado.aluno == aluno
    assert chamado.categoria == "tecnico" and chamado.prioridade == "alta"
    assert cliente_aluno.get(reverse("conta:chamado", args=[chamado.pk])).status_code == 200


def test_fila_do_suporte_e_do_painel(cliente_equipe, rede, admin_do_painel):
    servicos.abrir_chamado(
        rede=rede,
        titulo="Preciso de ajuda",
        descricao="Detalhe",
        prioridade="urgente",
        aberto_por=admin_do_painel,
    )
    resposta = cliente_equipe.get(reverse("conta:fila_suporte"))
    assert resposta.status_code == 200
    corpo = resposta.content.decode()
    assert "Preciso de ajuda" in corpo and "urgente" in corpo.lower()


def test_aluno_nao_entra_na_fila_do_suporte(cliente_aluno):
    assert cliente_aluno.get(reverse("conta:fila_suporte")).status_code == 403


def test_responder_pela_fila_do_suporte(cliente_equipe, rede, admin_do_painel):
    chamado = servicos.abrir_chamado(
        rede=rede, titulo="Sem internet", descricao="Detalhe", aberto_por=admin_do_painel
    )
    resposta = cliente_equipe.post(
        reverse("conta:responder_chamado", args=[chamado.pk]),
        {"acao": "responder", "texto": "Reiniciado o roteador"},
    )
    assert resposta.status_code == 302
    chamado.refresh_from_db()
    assert chamado.situacao == ChamadoDeSuporte.Situacao.EM_ANDAMENTO
    assert chamado.mensagens.count() == 1
