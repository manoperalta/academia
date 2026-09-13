"""Apoio aos testes: preenchimento de campos obrigatorios e criacao por rede.

Por que isto existe: a base atual nao tem factories por modelo e varios modelos
exigem campos. Em vez de escrever factory para cada um (e manter isso para
sempre), os testes gerais preenchem o minimo obrigatorio de forma generica --
o que tambem faz um teste novo passar a cobrir um modelo novo automaticamente.
"""

from __future__ import annotations

import itertools
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone

CONTADOR = itertools.count(1)


def _valor_para(campo):
    unico = getattr(campo, "unique", False)
    sufixo = f"-{next(CONTADOR)}" if unico else ""
    interno = campo.get_internal_type()
    if interno in {"CharField", "SlugField"}:
        return f"teste{sufixo}"[: campo.max_length or 50]
    if interno in {"TextField", "JSONField"}:
        return "teste" if interno == "TextField" else {}
    if interno in {"IntegerField", "BigIntegerField", "SmallIntegerField", "PositiveIntegerField"}:
        return next(CONTADOR)
    if interno in {"DecimalField", "FloatField"}:
        return Decimal("10.00")
    if interno == "BooleanField":
        return False
    if interno == "DateField":
        return date.today()
    if interno == "DateTimeField":
        return timezone.now()
    if interno == "EmailField":
        return f"teste{sufixo}@exemplo.com"
    if interno in {"FileField", "ImageField"}:
        return "testes/arquivo.txt"
    if interno in {"DurationField"}:
        return timezone.timedelta(minutes=30)
    return "teste"


def _instancia_para(modelo, rede=None, unidade=None, profundidade=0):
    if profundidade > 2:
        return None
    if modelo._meta.label_lower == "accounts.customuser" or modelo is get_user_model():
        return get_user_model().objects.get_or_create(
            username=f"usuario-{next(CONTADOR)}",
            defaults={"email": f"usuario{next(CONTADOR)}@exemplo.com"},
        )[0]
    from core.models import TenantModel

    if issubclass(modelo, TenantModel):
        return modelo.todos.create(**preencher_obrigatorios(modelo, rede=rede, unidade=unidade))
    return modelo.objects.create(**preencher_obrigatorios(modelo, profundidade=profundidade + 1))


def preencher_obrigatorios(modelo, *, rede=None, unidade=None, profundidade=0, **extras):
    """Dados minimos para criar uma instancia do modelo (sem tocar em rede/unidade)."""
    dados: dict = {}
    for campo in modelo._meta.concrete_fields:
        if campo.primary_key or campo.auto_created or campo.name in extras:
            continue
        if campo.name in {"rede", "unidade", "arquivado_em"}:
            continue
        if campo.null or campo.blank or campo.has_default():
            continue
        if campo.is_relation:
            dados[campo.name] = _instancia_para(
                campo.related_model, rede=rede, unidade=unidade, profundidade=profundidade
            )
        else:
            dados[campo.name] = _valor_para(campo)
    if rede is not None and any(f.name == "rede" for f in modelo._meta.concrete_fields):
        dados["rede"] = rede
    if unidade is not None and any(f.name == "unidade" for f in modelo._meta.concrete_fields):
        dados["unidade"] = unidade
    dados.update(extras)
    return dados


def criar(modelo, *, rede=None, unidade=None, **extras):
    """Cria um registro aceitando qualquer modelo de rede."""
    dados = preencher_obrigatorios(modelo, rede=rede, unidade=unidade, **extras)
    gerenciador = modelo.todos if hasattr(modelo, "todos") else modelo.objects
    return gerenciador.create(**dados)


def modelos_de_rede():
    """Todos os modelos concretos que herdam de TenantModel (descoberta automatica)."""
    from django.apps import apps

    from core.models import TenantModel

    encontrados = []
    for modelo in apps.get_models():
        if issubclass(modelo, TenantModel) and not modelo._meta.abstract:
            encontrados.append(modelo)
    return sorted(encontrados, key=lambda m: m._meta.label_lower)


def modelos_sem_rede_em_modelos():
    """Modelos de negocio que ainda nao herdam de TenantModel (deve ficar vazio)."""
    from django.apps import apps

    from core.models import TenantModel

    ignorados = {
        "remuneracao.regradecomissao",
        "remuneracao.apuracaodecomissao",
        "gamificacao.regradepontos",
        "gamificacao.saldodepontos",
        "gamificacao.conquista",
        "nps.pesquisa",
        "area_do_aluno.checkindoaluno",
        "remuneracao.itemdecomissao",
        "gamificacao.lancamentodepontos",
        "gamificacao.conquistadoaluno",
        "nps.resposta",
        "accounts.customuser",
        "api.apitoken",
        "api.registroauditoria",
        "api.webhookdesaida",
        "api.entregadewebhook",
        "api.tarefaassincrona",
        "documentos.envelopedeassinatura",
        "documentos.signatario",
        "documentos.assinatura",
        "pdv.produto",
        "pdv.venda",
        "pdv.itemdavenda",
        "pdv.movimentodeestoque",
        "fiscal.configuracaofiscal",
        "fiscal.notafiscal",
        "fiscal.eventofiscal",
        "cobranca.autorizacaodedebito",
        "cobranca.cobrancarecorrente",
        "cobranca.eventodacobranca",
        "acesso.dispositivodeacesso",
        "acesso.credencialdeacesso",
        "acesso.registrodeacesso",
        "acesso.planodeparceiro",
        "acesso.extratodeparceiro",
        "acesso.linhadeextrato",
        "relacionamento.lead",
        "relacionamento.interacaocomlead",
        "relacionamento.perfilderisco",
        "midia.arquivodemidia",
        "midia.partedemidia",
    }
    pendentes = []
    for modelo in apps.get_models():
        rotulo = modelo._meta.label_lower
        if rotulo in ignorados or modelo._meta.abstract:
            continue
        if issubclass(modelo, TenantModel):
            continue
        if modelo._meta.app_label in {
            "auth",
            "admin",
            "sessions",
            "contenttypes",
            "core",
            "governanca",
            "plataforma",
            "rede",
        }:
            continue
        pendentes.append(rotulo)
    return pendentes
