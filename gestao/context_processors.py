"""Menu do painel disponivel em qualquer template."""

from __future__ import annotations

from core.models import Unidade
from core.tenancy import unidades_do_usuario
from gestao.menu import ROTAS
from gestao.permissoes import Modulo, modulos_visiveis, nivel


def menu_do_painel(request):
    """Devolve os modulos visiveis para o usuario atual (usado pela barra lateral)."""
    usuario = getattr(request, "user", None)
    if not usuario or not usuario.is_authenticated:
        return {"menu_painel": [], "pode_painel_de_gestao": False, "unidades_disponiveis": []}
    rede = getattr(request, "rede", None)
    unidade = getattr(request, "unidade", None)
    itens = []
    for modulo in modulos_visiveis(usuario, rede=rede, unidade=unidade):
        itens.append(
            {
                "modulo": modulo.value,
                "rotulo": modulo.label,
                "rota": ROTAS.get(modulo, ""),
                "nivel": nivel(usuario, modulo.value, rede=rede, unidade=unidade),
                "icone": ICONES.get(modulo, "•"),
            }
        )
    return {
        "menu_painel": itens,
        # entrada do painel de gestao: so quem tem ao menos um modulo liberado ve o atalho
        "pode_painel_de_gestao": bool(itens),
        # seletor de unidade do topo: o usuario escolhe a unidade ativa da sessao
        "unidades_disponiveis": unidades_para_troca(usuario, rede),
    }


#: Icones simples (emoji) para a barra lateral, sem dependencia de biblioteca externa.
ICONES = {
    "privacidade": "🛡️",
    "dominio": "🌐",
    "rede": "🏬",
    "unidades": "🏢",
    "repasses": "💸",
    "governanca": "⚖️",
    "comunicados": "📣",
    "aprovacoes": "✅",
    "catalogo": "📚",
    Modulo.VISAO_GERAL: "📊",
    Modulo.ALUNOS: "🙋",
    Modulo.PROFESSORES: "🧑‍🏫",
    Modulo.AULAS: "🎬",
    Modulo.AGENDA: "🗓️",
    Modulo.FINANCEIRO: "💰",
    Modulo.RELATORIOS: "📈",
    Modulo.COMUNICACAO: "✉️",
    Modulo.IDENTIDADE: "🏷️",
    Modulo.EQUIPE: "👥",
    Modulo.PLANO: "💳",
    Modulo.AUDITORIA: "🔒",
    Modulo.INTEGRACOES: "🔌",
}


def unidades_para_troca(usuario, rede) -> list:
    """Unidades que o usuario pode escolher no seletor do topo.

    Equipe da plataforma ve todas as unidades da rede ativa; os demais veem apenas as
    unidades em que tem vinculo (o professor atende uma ou mais unidades).
    """
    if rede is None or not getattr(usuario, "is_authenticated", False):
        return []
    if usuario.is_superuser or usuario.is_staff:
        return list(Unidade.todos.filter(rede=rede).order_by("nome"))
    return list(unidades_do_usuario(usuario))
