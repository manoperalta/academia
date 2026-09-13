"""
Resolucao da rede/unidade de uma requisicao.

Prioridade (a primeira que existir vence):

1. ``?rede=<slug>`` / ``?unidade=<id>``  -- usado por suporte e testes;
2. sessao (rede/unidade escolhidas na troca de contexto);
3. vinculo do usuario autenticado (``core.VinculoUsuario``);
4. slug na URL (``/a/<slug>/...``) quando o roteamento por rede existir;
5. dominio (``Rede.dominio``) -- subdominio ou dominio proprio;
6. rede padrao da instalacao (compatibilidade com a operacao de rede unica).

O ponto 6 e o que mantem a instalacao atual funcionando sem nenhuma mudanca de
comportamento: enquanto nao existirem varias redes, tudo cai na rede padrao.
"""

from __future__ import annotations

from django.db import transaction

from core.context import definir_contexto
from core.models import Rede, Unidade, VinculoUsuario
from core.papeis import PAPEIS_DA_REDE

SLUG_REDE_PADRAO = "padrao"
NOME_REDE_PADRAO = "Academia (rede padrao)"

_CACHE_PADRAO = {"rede_id": None}


def rede_padrao() -> Rede | None:
    """Rede padrao da instalacao, criada na primeira necessidade.

    A existencia e conferida a cada chamada (uma consulta por PK, barata) para
    nao guardar referencia morta depois de rollback de teste ou restore.
    """
    if (
        _CACHE_PADRAO["rede_id"] is not None
        and Rede.todos.filter(pk=_CACHE_PADRAO["rede_id"]).exists()
    ):
        return Rede.todos.get(pk=_CACHE_PADRAO["rede_id"])
    with transaction.atomic():
        rede, _ = Rede.todos.get_or_create(
            slug=SLUG_REDE_PADRAO,
            defaults={"nome": NOME_REDE_PADRAO},
        )
    _CACHE_PADRAO["rede_id"] = rede.pk
    return rede


def unidades_do_usuario(usuario):
    """Unidades que o usuario pode acessar (queryset, pode ser vazia)."""
    if not usuario or not usuario.is_authenticated:
        return Unidade.todos.none()
    if usuario.is_superuser:
        return Unidade.todos.all()
    vinculos = VinculoUsuario.todos.filter(usuario=usuario, ativo=True)
    papeis_rede = vinculos.filter(unidade__isnull=True)
    if papeis_rede.exists():
        rede_ids = list(papeis_rede.values_list("rede_id", flat=True))
        return Unidade.todos.filter(rede_id__in=rede_ids)
    return Unidade.todos.filter(vinculos__usuario=usuario, vinculos__ativo=True).distinct()


def rede_do_usuario(usuario):
    """Primeira rede (ou a rede do primeiro vinculo) do usuario."""
    if not usuario or not usuario.is_authenticated:
        return None
    if usuario.is_superuser:
        return Rede.todos.order_by("pk").first()
    vinculo = (
        VinculoUsuario.todos.filter(usuario=usuario, ativo=True).select_related("rede").first()
    )
    return vinculo.rede if vinculo else None


def _do_parametro(request):
    slug = request.GET.get("rede")
    if slug:
        return Rede.todos.filter(slug=slug).first(), None
    return None, None


def _da_sessao(request):
    rede_id = request.session.get("rede_id") if hasattr(request, "session") else None
    unidade_id = request.session.get("unidade_id") if hasattr(request, "session") else None
    if not rede_id:
        return None, None
    rede = Rede.todos.filter(pk=rede_id).first()
    unidade = Unidade.todos.filter(pk=unidade_id).first() if unidade_id else None
    return rede, unidade


def _do_dominio(request):
    host = request.get_host().split(":")[0].lower()
    if not host:
        return None
    return Rede.todos.filter(dominio=host).first(), None


def resolver_rede(request):
    """Devolve ``(rede, unidade)`` para a requisicao (rede nunca None em uso normal)."""
    # Subdominio do cliente ou dominio proprio (RF-PLT-050)
    try:
        from governanca.servicos import rede_por_host

        host = request.get_host()
    except Exception:
        host = ""
    if host:
        rede_do_host = rede_por_host(host)
        if rede_do_host is not None:
            return rede_do_host
    rede, unidade = _do_parametro(request)
    if rede:
        return rede, unidade

    rede, unidade = _da_sessao(request)
    if rede:
        return rede, unidade

    # Suporte: sessao com impersonation ativa entra na visao do cliente.
    impersonacao = _impersonacao_da_sessao(request)
    if impersonacao is not None:
        return impersonacao.rede, None

    usuario = getattr(request, "user", None)
    if usuario is not None and usuario.is_authenticated:
        rede = rede_do_usuario(usuario)
        if rede:
            vinculos = VinculoUsuario.todos.filter(usuario=usuario, rede=rede, ativo=True)
            papeis_de_rede_do_usuario = set(vinculos.values_list("papel", flat=True))
            # Papeis de rede veem todas as unidades; a unidade entra pela sessao.
            if usuario.is_superuser or (papeis_de_rede_do_usuario & PAPEIS_DA_REDE):
                return rede, None
            vinculo = vinculos.select_related("unidade").first()
            return rede, (vinculo.unidade if vinculo else None)

    rede = _do_dominio(request)[0]
    if rede:
        return rede, None

    return rede_padrao(), None


def definir_contexto_da_requisicao(request) -> None:
    """Resolve e instala o contexto da requisicao."""
    rede, unidade = resolver_rede(request)
    definir_contexto(rede=rede, unidade=unidade, usuario=getattr(request, "user", None))
    request.rede = rede
    request.unidade = unidade


def _impersonacao_da_sessao(request):
    """Impersonation ativa na sessao (import tardio evita ciclo com a plataforma)."""
    if not hasattr(request, "session"):
        return None
    identificador = request.session.get("impersonacao_id")
    if not identificador:
        return None
    from plataforma.models import Impersonacao

    return Impersonacao.objects.filter(pk=identificador, fim__isnull=True).first()
