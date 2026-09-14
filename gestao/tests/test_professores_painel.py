"""Cadastro de professor: somente pelo painel (admin da rede / gestor da unidade), com foto real.

Requisitos de produto cobertos aqui:
- o cadastro de professor acontece no painel -- nao ha caminho alternativo (o atalho legado
  redireciona para o painel e nao cria mais registro);
- a foto de perfil e imagem de verdade, ate 5 MB (o teto e conferido por nos; o formato, pelo
  proprio ``ImageField`` do Django, que abre o arquivo com o Pillow);
- professor nao cadastra professor; gestor de unidade cadastra.
"""

from __future__ import annotations

from io import BytesIO

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image

from core.models import VinculoUsuario
from core.papeis import Papel
from professores.models import Professor

EXE = b"MZ\x90\x00" + b"\x00" * 64


def _erros(resposta):
    """Mostra o erro do formulario quando o POST nao passa (diagnostico do teste)."""
    formulario = getattr(resposta, "context", None) and resposta.context.get("form")
    return f"form invalido: {formulario.errors if formulario else 'sem formulario no contexto'}"


def _png(largura: int = 10, altura: int = 10) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (largura, altura), (120, 200, 140)).save(buffer, format="PNG")
    return buffer.getvalue()


def _png_acima_do_limite() -> bytes:
    """PNG de verdade com mais de 5 MB (ruido nao comprime bem)."""
    import os

    largura, altura = 1800, 1800
    imagem = Image.frombytes("RGB", (largura, altura), os.urandom(largura * altura * 3))
    buffer = BytesIO()
    imagem.save(buffer, format="PNG")
    dados = buffer.getvalue()
    assert len(dados) > 5 * 1024 * 1024
    return dados


@pytest.fixture(autouse=True)
def media_temporaria(tmp_path, settings):
    """A foto do teste nao vai para o MEDIA_ROOT do projeto."""
    settings.MEDIA_ROOT = tmp_path
    return tmp_path


def _payload(**extra):
    dados = {
        "nome": "Professor Teste",
        "email_prof": "prof.teste@exemplo.com",
        "telefone_prof": "51999990000",
        "status_prof": "Ativo",
        "criar_login": "on",
    }
    dados.update(extra)
    return dados


def test_admin_da_rede_cadastra_professor_com_foto(cliente_logado, rede):
    foto = SimpleUploadedFile("foto.png", _png(), content_type="image/png")
    resposta = cliente_logado.post(
        reverse("gestao:professor_novo"), {**_payload(), "foto_prof": foto}
    )
    assert resposta.status_code == 302, _erros(resposta)
    professor = Professor.todos.get(nome="Professor Teste")
    assert professor.rede_id == rede.pk
    assert professor.foto_prof.name.endswith(".png")
    assert professor.arquivado_em is None


def test_gestor_da_unidade_cadastra_professor(db, client, rede, unidade):
    gestor = get_user_model().objects.create_user(
        username="gestor.unidade", password="senha-de-teste-123"
    )
    VinculoUsuario.todos.create(
        usuario=gestor, rede=rede, unidade=unidade, papel=Papel.GESTOR_UNIDADE
    )
    client.force_login(gestor)
    resposta = client.get(reverse("gestao:professor_novo"))
    assert resposta.status_code == 200
    resposta = client.post(
        reverse("gestao:professor_novo"),
        {**_payload(nome="Professor do Gestor"), "foto_prof": SimpleUploadedFile("f.png", _png())},
    )
    assert resposta.status_code == 302, _erros(resposta)
    assert Professor.todos.filter(nome="Professor do Gestor").exists()


def test_recepcao_nao_cadastra_professor(cliente_recepcao):
    """A recepcao ve a lista, mas nao cadastra (matriz de permissoes)."""
    assert cliente_recepcao.get(reverse("gestao:professor_novo")).status_code == 403


def test_professor_nao_cadastra_professor(cliente_professor):
    assert cliente_professor.get(reverse("gestao:professor_novo")).status_code == 403


def test_aluno_nao_cadastra_professor(cliente_aluno):
    assert cliente_aluno.get(reverse("gestao:professor_novo")).status_code == 403


def test_foto_acima_de_5mb_e_recusada(cliente_logado):
    grande = SimpleUploadedFile("foto.png", _png_acima_do_limite(), content_type="image/png")
    resposta = cliente_logado.post(
        reverse("gestao:professor_novo"), {**_payload(), "foto_prof": grande}
    )
    assert resposta.status_code == 200, _erros(resposta)
    assert not Professor.todos.filter(nome="Professor Teste").exists()
    assert "5.0 MB" in resposta.content.decode(), _erros(resposta)


def test_arquivo_que_nao_e_imagem_e_recusado(cliente_logado):
    falso = SimpleUploadedFile("foto.png", EXE, content_type="image/png")
    resposta = cliente_logado.post(
        reverse("gestao:professor_novo"), {**_payload(), "foto_prof": falso}
    )
    assert resposta.status_code == 200
    assert not Professor.todos.exists()
    assert "imagem" in resposta.content.decode()


def test_cadastro_de_professor_no_dashboard_respeita_a_matriz(
    cliente_logado, cliente_recepcao, cliente_aluno
):
    """14/09/2026: a tela sai do painel e passa a ser a mesma casca do cadastro de aluno.

    A protecao continua identica -- quem nao tem o modulo PROFESSORES em nivel de edicao
    recebe 403 (antes, a tela so existia no painel de gestao).
    """
    resposta = cliente_logado.get("/professores/novo/")
    assert resposta.status_code == 200
    assert reverse("professor_list") in resposta.content.decode()
    assert "cdn.tailwindcss.com" not in resposta.content.decode()
    assert cliente_recepcao.get("/professores/novo/").status_code == 403
    assert cliente_aluno.get("/professores/novo/").status_code == 403


def test_perfil_do_professor_nao_cria_cadastro_sozinho(db, client, usuario, vinculo_admin):
    """Quem nao tem cadastro de professor e encaminhado ao painel, sem criar registro."""
    client.force_login(usuario)
    resposta = client.post(reverse("complete_profile_professor"), _payload(nome="Auto Cadastro"))
    assert resposta.status_code == 302
    assert not Professor.todos.exists()
