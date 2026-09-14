"""Menu do painel disponivel em qualquer template."""

from __future__ import annotations

from gestao.menu import ROTAS
from gestao.permissoes import Modulo, modulos_visiveis, nivel


def menu_do_painel(request):
    """Devolve os modulos visiveis para o usuario atual (usado pela barra lateral)."""
    usuario = getattr(request, "user", None)
    if not usuario or not usuario.is_authenticated:
        return {"menu_painel": []}
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
    return {"menu_painel": itens}


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
