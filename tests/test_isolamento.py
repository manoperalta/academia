"""Isolamento entre redes e unidades -- o teste que bloqueia o go-live (RNF-028).

Se algum destes testes falhar, NAO suba: significa que um cliente pode ver dado
de outro.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model

from core.context import usar_rede
from core.models import Rede, Unidade, VinculoUsuario
from core.papeis import Papel
from tests.apoio import criar, modelos_de_rede, modelos_sem_rede_em_modelos

pytestmark = pytest.mark.isolamento


def test_todo_modelo_de_negocio_herda_de_tenant_model():
    """Nenhum modelo de negocio pode ficar fora do escopo de rede."""
    pendentes = modelos_sem_rede_em_modelos()
    assert pendentes == [], f"modelos sem rede: {pendentes}"


def test_todo_modelo_de_rede_tem_rede_indexada():
    """A chave de isolamento precisa existir e ser indexada em todos os modelos."""
    problemas = []
    for modelo in modelos_de_rede():
        campo = modelo._meta.get_field("rede")
        if not campo.db_index:
            problemas.append(f"{modelo.__name__}: rede sem indice")
        if not campo.null:
            problemas.append(f"{modelo.__name__}: rede obrigatoria (fase 1 mantem opcional)")
    assert problemas == [], problemas


@pytest.mark.django_db
def test_objects_respeita_a_rede_do_contexto(rede, outra_rede):
    """Com contexto de rede, o manager padrao nao enxerga a outra rede."""
    from aulas.models import Aulas

    with usar_rede(rede):
        minha = criar(Aulas, rede=rede)
    with usar_rede(outra_rede):
        criar(Aulas, rede=outra_rede)

    with usar_rede(rede):
        encontrados = list(Aulas.objects.all())
        assert [a.pk for a in encontrados] == [minha.pk]
        assert Aulas.todos.count() == 2  # o manager sem escopo enxerga tudo


@pytest.mark.django_db
def test_models_de_rede_criam_com_a_rede_do_contexto(rede):
    """Sem informar rede, o registro nasce na rede do contexto (compatibilidade)."""
    from aulas.models import Aulas

    with usar_rede(rede):
        aula = criar(Aulas)
    assert aula.rede_id == rede.pk


@pytest.mark.django_db
def test_unidades_da_mesma_rede_nao_se_misturam(rede, unidade):
    """Dentro da mesma rede, o recorte por unidade funciona."""
    outra_unidade = Unidade.todos.create(rede=rede, nome="Unidade Sul", codigo="sul")
    from usuarios.models import Usuario

    with usar_rede(rede, unidade=unidade):
        aluno_a = criar(Usuario, rede=rede, unidade=unidade)
    with usar_rede(rede, unidade=outra_unidade):
        aluno_b = criar(Usuario, rede=rede, unidade=outra_unidade)

    assert aluno_a.pk != aluno_b.pk
    with usar_rede(rede, unidade=unidade):
        escopado = list(Usuario.objects.escopo_unidade())
        assert [a.pk for a in escopado] == [aluno_a.pk]


@pytest.mark.django_db
def test_vinculo_de_uma_rede_nao_vale_na_outra(rede, outra_rede, usuario):
    """O mesmo usuario em duas redes tem papeis independentes."""
    VinculoUsuario.todos.create(usuario=usuario, rede=rede, papel=Papel.GESTOR_UNIDADE)
    assert usuario.vinculos.filter(rede=rede, ativo=True).count() == 1
    assert usuario.vinculos.filter(rede=outra_rede).count() == 0


@pytest.mark.django_db
def test_rede_padrao_atende_instalacao_de_rede_unica():
    """Sem contexto e sem vinculo, a instalacao continua operando (rede padrao)."""
    from core.tenancy import rede_padrao

    padrao = rede_padrao()
    assert padrao.pk is not None
    assert padrao.slug == "padrao"
    assert Rede.todos.filter(slug="padrao").count() == 1


@pytest.mark.django_db
def test_superusuario_enxerga_tudo_via_manager_sem_escopo(rede, outra_rede, usuario):
    """O manager ``todos`` e a saida explicita para codigo de plataforma."""
    usuario.is_superuser = True
    usuario.is_staff = True
    usuario.save()
    assert get_user_model().objects.filter(pk=usuario.pk).exists()
    assert Rede.todos.count() == 2
