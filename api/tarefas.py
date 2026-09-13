"""Tarefas assincronas: relatorio, importacao, exportacao e LGPD (RF-API-012/015/016)."""

from __future__ import annotations

import csv
import json
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from api.models import TarefaAssincrona

#: Quanto tempo o link de download continua valido.
VALIDADE_DO_ARQUIVO = timedelta(days=2)


class TarefaDesconhecida(Exception):
    """Tipo de tarefa nao registrado."""


def _pasta() -> Path:
    """Pasta dos artefatos das tarefas (CSV do relatorio).

    Fica dentro de ``MEDIA_ROOT`` de proposito: artefato gerado em execucao nao pode cair no
    diretorio do codigo -- o caminho relativo sujava a arvore do repositorio a cada execucao.
    """
    pasta = Path(getattr(settings, "TAREFAS_DIR", Path(settings.MEDIA_ROOT) / "tarefas"))
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def enfileirar(tipo: str, rede=None, parametros=None, usuario=None, token=None) -> TarefaAssincrona:
    if tipo not in TarefaAssincrona.Tipo.values:
        raise TarefaDesconhecida(tipo)
    return TarefaAssincrona.objects.create(
        rede=rede,
        tipo=tipo,
        parametros=parametros or {},
        solicitado_por=usuario if getattr(usuario, "pk", None) else None,
        token=token if getattr(token, "pk", None) else None,
    )


def _resolver_rede(conteudo: dict):
    from core.models import Rede

    if conteudo.get("rede") is not None:
        return conteudo["rede"]
    identificador = conteudo.get("rede_id")
    return Rede.todos.filter(pk=identificador).first() if identificador else None


def _data_iso(valor):
    from datetime import date

    return valor if isinstance(valor, date) else date.fromisoformat(str(valor))


def _relatorio(conteudo: dict) -> dict:
    from rede.servicos import comparativo_entre_unidades, consolidado_da_rede

    rede = _resolver_rede(conteudo)
    inicio = _data_iso(conteudo["inicio"])
    fim = _data_iso(conteudo["fim"])
    consolidado = consolidado_da_rede(rede, inicio, fim)
    linhas = [
        [
            "Unidade",
            "Recebido",
            "A receber",
            "Inadimplencia %",
            "Alunos ativos",
            "Ticket medio",
            "Repasse",
            "Despesas",
        ],
        *[
            [
                linha["unidade"].nome,
                str(linha["recebido"]),
                str(linha["em_aberto"]),
                str(linha["inadimplencia"]),
                linha["alunos_ativos"],
                str(linha["ticket_medio"]),
                str(linha["repasse"]),
                str(linha["despesas"]),
            ]
            for linha in comparativo_entre_unidades(rede, inicio, fim)
        ],
        [],
        ["Total recebido", str(consolidado["recebido"])],
        ["Resultado", str(consolidado["resultado"])],
    ]
    return {
        "tipo": "relatorio_rede",
        "linhas": linhas,
        "resumo": {
            "recebido": str(consolidado["recebido"]),
            "resultado": str(consolidado["resultado"]),
            "unidades": consolidado["unidades"],
        },
    }


def _exportacao(conteudo: dict) -> dict:
    from django.apps import apps

    rede = _resolver_rede(conteudo)
    if conteudo.get("recurso") == "webhooks":
        linhas = [
            ["evento", "entrega", "situacao", "tentativas"],
            *[list(item) for item in conteudo.get("linhas", [])],
        ]
        return {"tipo": "exportacao_webhooks", "linhas": linhas}
    tabelas = {}
    for modelo in apps.get_models():
        if not hasattr(modelo, "todos") or not any(
            campo.name == "rede" for campo in modelo._meta.get_fields()
        ):
            continue
        registros = modelo.todos.filter(rede=rede) if rede else modelo.todos.all()
        tabelas[modelo._meta.label_lower] = registros.count()
    return {"tipo": "exportacao_contagens", "linhas": [["tabela", "registros"], *tabelas.items()]}


def _lgpd(conteudo: dict) -> dict:
    from governanca.servicos import anonimizar_titular, dados_do_titular
    from usuarios.models import Usuario

    rede = _resolver_rede(conteudo)
    aluno = conteudo.get("aluno") or Usuario.todos.filter(pk=conteudo.get("aluno_id")).first()
    if aluno is None:
        raise ValueError("titular nao encontrado para a tarefa de LGPD")
    if conteudo.get("acao") == "anonimizar":
        resultado = anonimizar_titular(rede, aluno, usuario=conteudo.get("usuario"))
        return {
            "tipo": "lgpd_anonimizacao",
            "linhas": [["acao", "resultado"], ["anonimizar", resultado.get("titular", "ok")]],
        }
    dados = dados_do_titular(rede, aluno)
    return {
        "tipo": "lgpd_exportacao",
        "linhas": [
            ["campo", "valor"],
            *[
                [chave, json.dumps(valor, ensure_ascii=False)[:200]]
                for chave, valor in dados.items()
            ],
        ],
    }


def _importacao(conteudo: dict) -> dict:
    from gestao.importacao import analisar_aplicar_multiunidade

    resultado = analisar_aplicar_multiunidade(
        conteudo["conteudo"],
        _resolver_rede(conteudo),
        tipo=conteudo.get("tipo", "alunos"),
        dry_run=bool(conteudo.get("dry_run")),
    )
    return {
        "tipo": "importacao",
        "linhas": [
            ["unidade", "criados", "erros"],
            *[
                [nome, dados["criados"], len(dados["erros"])]
                for nome, dados in resultado["por_unidade"].items()
            ],
        ],
        "resumo": {
            "criados": resultado["criados"],
            "erros": resultado["erros"],
            "dry_run": bool(conteudo.get("dry_run")),
        },
    }


EXECUTORES = {
    TarefaAssincrona.Tipo.RELATORIO: _relatorio,
    TarefaAssincrona.Tipo.EXPORTACAO: _exportacao,
    TarefaAssincrona.Tipo.LGPD: _lgpd,
    TarefaAssincrona.Tipo.IMPORTACAO: _importacao,
}


def executar(tarefa: TarefaAssincrona) -> TarefaAssincrona:
    """Roda uma tarefa, grava o CSV e o resultado (chamado pela rotina de jobs)."""
    tarefa.situacao = TarefaAssincrona.Situacao.RODANDO
    tarefa.progresso = 10
    tarefa.save(update_fields=["situacao", "progresso", "atualizado_em"])
    try:
        conteudo = dict(tarefa.parametros or {})
        executor = EXECUTORES.get(tarefa.tipo)
        if executor is None:
            raise TarefaDesconhecida(tarefa.tipo)
        resultado = executor(conteudo)
        caminho = _pasta() / f"tarefa-{tarefa.pk}-{timezone.now():%Y%m%d%H%M%S}.csv"
        with caminho.open("w", newline="", encoding="utf-8") as arquivo:
            escritor = csv.writer(arquivo)
            escritor.writerows(resultado["linhas"])
        tarefa.resultado = resultado.get("resumo", {"linhas": len(resultado["linhas"])})
        tarefa.arquivo = str(caminho)
        tarefa.progresso = 100
        tarefa.situacao = TarefaAssincrona.Situacao.CONCLUIDA
        tarefa.termina_em = timezone.now() + VALIDADE_DO_ARQUIVO
    except Exception as excecao:
        tarefa.situacao = TarefaAssincrona.Situacao.FALHOU
        tarefa.erro = str(excecao)[:1000]
        tarefa.progresso = 100
    tarefa.save()
    return tarefa


def processar_pendentes(limite: int = 10) -> dict:
    """Processa a fila (chamado pela rotina de jobs, de hora em hora)."""
    concluidas = falhas = 0
    for tarefa in TarefaAssincrona.objects.filter(
        situacao=TarefaAssincrona.Situacao.NA_FILA
    ).order_by("criado_em")[:limite]:
        tarefa = executar(tarefa)
        if tarefa.situacao == TarefaAssincrona.Situacao.CONCLUIDA:
            concluidas += 1
        else:
            falhas += 1
    vencidas = TarefaAssincrona.objects.filter(
        situacao=TarefaAssincrona.Situacao.CONCLUIDA, termina_em__lt=timezone.now()
    ).update(arquivo="")
    return {"concluidas": concluidas, "falhas": falhas, "arquivos_expirados": vencidas}