"""Busca global do painel: um termo, varios recursos, sempre dentro do que o usuario pode ver.

Duas regras que evitam a busca virar vazamento de dado:

* o recorte e sempre pela **rede** de quem esta logado;
* cada fonte declara o **modulo** de que depende e a busca **pula** a fonte quando o papel do
  usuario nao alcanca aquele modulo — quem nao ve financeiro nao acha pagamento pela busca.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from django.db.models import Q
from django.urls import NoReverseMatch, reverse

from gestao.permissoes import Modulo, pode

TERMO_MINIMO = 2


@dataclass
class Resultado:
    grupo: str
    titulo: str
    descricao: str
    url: str
    modulo: str | None = None


def _url(candidatos: list[tuple[str, list]]) -> str:
    """Primeiro nome de rota que resolver (o projeto tem telas com nomes historicos)."""
    for nome, argumentos in candidatos:
        try:
            return reverse(nome, args=argumentos)
        except NoReverseMatch:
            continue
    return ""


def _alunos(rede, termo: str) -> list[Resultado]:
    from usuarios.models import Usuario

    consulta = (
        Usuario.todos.filter(rede=rede)
        .filter(
            Q(nome__icontains=termo)
            | Q(user__username__icontains=termo)
            | Q(user__email__icontains=termo)
        )
        .select_related("user", "unidade")
    )
    resultados = []
    for aluno in consulta[:20]:
        resultados.append(
            Resultado(
                grupo="Alunos",
                titulo=aluno.nome or aluno.user.username,
                descricao=f"{aluno.get_status_display() if hasattr(aluno, 'get_status_display') else aluno.status_user}"
                f" · {aluno.unidade.nome if aluno.unidade else 'sem unidade'}",
                url=_url(
                    [
                        ("gestao:aluno_detalhe", [aluno.pk]),
                        ("gestao:aluno", [aluno.pk]),
                        ("gestao:alunos", []),
                    ]
                ),
                modulo=Modulo.ALUNOS,
            )
        )
    return resultados


def _unidades(rede, termo: str) -> list[Resultado]:
    from core.models import Unidade

    resultados = []
    for unidade in Unidade.objects.filter(rede=rede).filter(
        Q(nome__icontains=termo) | Q(codigo__icontains=termo) | Q(cidade__icontains=termo)
    ):
        resultados.append(
            Resultado(
                grupo="Unidades",
                titulo=unidade.nome,
                descricao=f"{unidade.codigo or 'sem codigo'} · {unidade.cidade or 'cidade nao informada'}"
                f"/{unidade.uf or ''}".rstrip("/"),
                url=_url([("gestao:unidades", []), ("rede:painel", [])]),
                modulo=None,
            )
        )
    return resultados


def _pagamentos(rede, termo: str) -> list[Resultado]:
    from financeiro.models import Pagamento

    consulta = Pagamento.todos.filter(rede=rede).select_related("usuario", "plano")
    resultados = []
    for pagamento in consulta.filter(plano__nome__icontains=termo)[:20]:
        resultados.append(
            Resultado(
                grupo="Pagamentos",
                titulo=f"{pagamento.plano.nome if pagamento.plano else 'Pagamento'} — "
                f"R$ {pagamento.valor_pago}",
                descricao=f"{pagamento.usuario} · {pagamento.status} · "
                f"vencimento {pagamento.data_fim:%d/%m/%Y}",
                url=_url([("gestao:pagamento_detalhe", [pagamento.pk]), ("gestao:pagamentos", [])]),
                modulo=Modulo.FINANCEIRO,
            )
        )
    return resultados


def _leads(rede, termo: str) -> list[Resultado]:
    from relacionamento.models import Lead

    consulta = Lead.objects.filter(rede=rede).filter(
        Q(nome__icontains=termo) | Q(telefone__icontains=termo) | Q(email__icontains=termo)
    )
    resultados = []
    for lead in consulta[:20]:
        resultados.append(
            Resultado(
                grupo="Leads",
                titulo=lead.nome,
                descricao=f"{lead.get_origem_display()} · {lead.get_situacao_display()}",
                url=_url([("relacionamento:lead", [lead.pk])]),
                modulo=Modulo.CRM,
            )
        )
    return resultados


def _midia(rede, termo: str) -> list[Resultado]:
    from midia.models import ArquivoDeMidia

    resultados = []
    for arquivo in ArquivoDeMidia.objects.filter(rede=rede, titulo__icontains=termo)[:20]:
        resultados.append(
            Resultado(
                grupo="Midia",
                titulo=arquivo.titulo,
                descricao=f"{arquivo.get_tipo_display()} · {arquivo.tamanho_legivel} · "
                f"{arquivo.get_situacao_display()}",
                url=_url([("midia:player", [arquivo.pk]), ("midia:lista", [])]),
                modulo=Modulo.AULAS,
            )
        )
    return resultados


def _risco(rede, termo: str) -> list[Resultado]:
    from relacionamento.models import PerfilDeRisco

    resultados = []
    for perfil in PerfilDeRisco.objects.filter(
        rede=rede, aluno__nome__icontains=termo
    ).select_related("aluno")[:20]:
        resultados.append(
            Resultado(
                grupo="Risco de evasao",
                titulo=perfil.aluno.nome,
                descricao=f"{perfil.pontuacao} pontos · {perfil.get_faixa_display()} · "
                f"{perfil.get_desfecho_display()}",
                url=_url([("relacionamento:risco", [perfil.pk])]),
                modulo=Modulo.RETENCAO,
            )
        )
    return resultados


def _comunicados(rede, termo: str) -> list[Resultado]:
    from rede.models import Comunicado

    resultados = []
    for comunicado in Comunicado.objects.filter(rede=rede, titulo__icontains=termo)[:20]:
        resultados.append(
            Resultado(
                grupo="Comunicados",
                titulo=comunicado.titulo,
                descricao="aviso da rede",
                url=_url([("rede:painel", [])]),
                modulo=None,
            )
        )
    return resultados


def _professores(rede, termo: str) -> list[Resultado]:
    from professores.models import Professor

    resultados = []
    for professor in Professor.todos.filter(rede=rede, nome__icontains=termo)[:20]:
        resultados.append(
            Resultado(
                grupo="Professores",
                titulo=professor.nome,
                descricao=getattr(professor, "status_prof", "") or "professor",
                url=_url([("gestao:professores", []), ("remuneracao:painel", [])]),
                modulo=None,
            )
        )
    return resultados


FONTES: list[Callable] = [
    _alunos,
    _unidades,
    _pagamentos,
    _leads,
    _midia,
    _risco,
    _comunicados,
    _professores,
]


def buscar(rede, termo: str, usuario=None, limite_por_grupo: int = 5) -> dict:
    """Procura o termo em cada fonte permitida ao usuario e agrupa o resultado."""
    termo = (termo or "").strip()
    if len(termo) < TERMO_MINIMO:
        return {"termo": termo, "grupos": [], "total": 0, "curto": True, "fontes_puladas": []}

    grupos: dict[str, list[Resultado]] = {}
    puladas: list[str] = []
    for fonte in FONTES:
        try:
            encontrados = fonte(rede, termo)
        except Exception:  # uma fonte quebrada nao derruba a busca inteira
            continue
        if not encontrados:
            continue
        modulo = encontrados[0].modulo
        if (
            modulo is not None
            and usuario is not None
            and not pode(usuario, modulo, "ver", rede=rede)
        ):
            puladas.append(encontrados[0].grupo)
            continue
        grupos[encontrados[0].grupo] = encontrados[:limite_por_grupo]

    total = sum(len(lista) for lista in grupos.values())
    return {
        "termo": termo,
        "grupos": [{"nome": nome, "resultados": lista} for nome, lista in grupos.items()],
        "total": total,
        "curto": False,
        "fontes_puladas": puladas,
    }
