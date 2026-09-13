"""Rotinas periodicas (jobs) com dry-run, registro de resultado e alerta em falha."""

from __future__ import annotations

import logging
import time

from django.utils import timezone

from governanca.models import RotinaAgendada

logger = logging.getLogger("governanca")


def _rotina_metricas(dry_run: bool) -> str:
    from governanca.servicos import agregar_metricas, alertas_pendentes

    if dry_run:
        return f"agregaria as metricas do cache; alertas atuais: {len(alertas_pendentes())}"
    gravadas = agregar_metricas()
    return f"{gravadas} linha(s) de metrica gravada(s); {len(alertas_pendentes())} alerta(s)"


def _rotina_backup(dry_run: bool) -> str:
    from governanca.servicos import (
        aplicar_retencao_de_backups,
        backup_vai_rodar_hoje,
        executar_backup,
        verificar_backup,
    )

    if dry_run:
        return "faria o backup do banco" if backup_vai_rodar_hoje() else "backup ja feito hoje"
    if not backup_vai_rodar_hoje():
        return "backup ja feito hoje"
    registro = executar_backup()
    if registro.situacao != "ok":
        raise RuntimeError(f"backup falhou: {registro.erro[:200]}")
    verificacao = verificar_backup(registro)
    aplicar_retencao_de_backups(dry_run=False)
    return f"backup {registro.tamanho_mb} MB verificado: {verificacao['detalhe']}"


def _rotina_faturas(dry_run: bool) -> str:
    from plataforma.servicos import gerar_faturas_do_dia

    if dry_run:
        return "emitiria as faturas vencendo hoje"
    criadas = gerar_faturas_do_dia()
    return f"{criadas} fatura(s) emitida(s)"


def _rotina_regua(dry_run: bool) -> str:
    from plataforma.servicos import rodar_regua

    if dry_run:
        return "rodaria a regua de cobranca"
    disparos = rodar_regua()
    return f"{disparos} disparo(s) da regua"


def _rotina_repasses(dry_run: bool) -> str:
    from rede.servicos import emitir_repasses_do_mes

    if dry_run:
        return "emitiria os repasses do mes por unidade"
    resultado = emitir_repasses_do_mes()
    return (
        f"{len(resultado['emitidos'])} repasse(s) do periodo "
        f"{resultado['inicio']:%d/%m} a {resultado['fim']:%d/%m}; "
        f"{len(resultado['erros'])} unidade(s) sem regra"
    )


def _rotina_retencao(dry_run: bool) -> str:
    from governanca.servicos import aplicar_retencao

    resultado = aplicar_retencao(dry_run=dry_run)
    if not resultado["regras"]:
        return "nada vencido para expurgar"
    return "; ".join(
        f"{regra['entidade']}: {regra['registros']} registro(s)" for regra in resultado["regras"]
    )


def _rotina_dominios(dry_run: bool) -> str:
    from core.models import Rede, StatusCertificado
    from governanca.servicos import reemitir_certificado, verificar_dominio

    com_dominio = list(Rede.todos.exclude(dominio=""))
    if dry_run:
        return f"verificaria {len(com_dominio)} dominio(s) proprio(s)"
    verificados = reemitidos = 0
    for rede in com_dominio:
        verificar_dominio(rede, forcar=True)
        verificados += 1
        if rede.certificado_status == StatusCertificado.ERRO and rede.dominio_status == "pronto":
            reemitir_certificado(rede)
            reemitidos += 1
    return f"{verificados} dominio(s) verificado(s); {reemitidos} certificado(s) marcado(s) para reemissao"


def _rotina_metas(dry_run: bool) -> str:
    from core.models import Rede
    from rede.servicos import atualizar_metas

    if dry_run:
        return "atualizaria o realizado das metas"
    total = sum(atualizar_metas(rede) for rede in Rede.todos.all())
    return f"{total} meta(s) recalculada(s)"


def _rotina_atrasos(dry_run: bool) -> str:
    from rede.servicos import atualizar_atrasados

    if dry_run:
        return "marcaria os repasses vencidos como atrasados"
    return f"{atualizar_atrasados()} repasse(s) marcado(s) como atrasado"


def _rotina_tarefas(dry_run: bool) -> str:
    from api.tarefas import processar_pendentes

    if dry_run:
        return "processaria a fila de relatorios/importacoes"
    resultado = processar_pendentes()
    return (
        f"{resultado['concluidas']} tarefa(s) concluida(s), {resultado['falhas']} falha(s), "
        f"{resultado['arquivos_expirados']} arquivo(s) expirado(s)"
    )


def _rotina_webhooks(dry_run: bool) -> str:
    from api.webhooks import entregar_pendentes

    if dry_run:
        return "entregaria os webhooks pendentes"
    resultado = entregar_pendentes()
    return (
        f"{resultado['entregues']} entrega(s) ok, {resultado['falhas']} com falha "
        f"(reentrega agendada com backoff)"
    )


#: nome -> (periodicidade, descricao, funcao)
ROTINAS = {
    "metricas": ("hora", "Agrega as metricas por cliente e checa alertas", _rotina_metricas),
    "backup": ("dia", "Backup do banco com verificacao por restauracao", _rotina_backup),
    "faturas": ("dia", "Emite as faturas dos clientes que vencem hoje", _rotina_faturas),
    "regua": ("dia", "Roda a regua de cobranca (avisos e bloqueio)", _rotina_regua),
    "repasses": ("mes", "Emite os repasses/royalties do mes por unidade", _rotina_repasses),
    "retencao": ("semana", "Aplica o expurgo conforme as regras de retencao", _rotina_retencao),
    "dominios": ("dia", "Verifica dominios proprios e reemite certificados", _rotina_dominios),
    "metas": ("dia", "Recalcula o realizado das metas da rede", _rotina_metas),
    "atrasos": ("dia", "Marca repasses vencidos como atrasados", _rotina_atrasos),
    "tarefas": ("hora", "Processa a fila de tarefas assincronas da API", _rotina_tarefas),
    "webhooks": (
        "hora",
        "Entrega os webhooks de saida pendentes (com reentrega)",
        _rotina_webhooks,
    ),
}


def sincronizar_rotinas() -> int:
    """Cria/atualiza o catalogo de rotinas no banco (idempotente)."""
    criadas = 0
    for nome, (periodicidade, descricao, _funcao) in ROTINAS.items():
        _rotina, criada = RotinaAgendada.objects.update_or_create(
            nome=nome,
            defaults={"periodicidade": periodicidade, "descricao": descricao},
        )
        criadas += int(criada)
    return criadas


def rotinas_devidas(agora=None) -> list[RotinaAgendada]:
    agora = agora or timezone.now()
    devidas = []
    for rotina in RotinaAgendada.objects.filter(ativa=True):
        if rotina.ultima_execucao is None:
            devidas.append(rotina)
            continue
        intervalos = {"hora": 3600, "dia": 86400, "semana": 604800, "mes": 2592000}
        if (agora - rotina.ultima_execucao).total_seconds() >= intervalos.get(
            rotina.periodicidade, 86400
        ):
            devidas.append(rotina)
    return devidas


def executar_rotinas(dry_run: bool = False, somente: str = "", agora=None) -> dict:
    """Roda as rotinas devidas, registrando resultado (e falha) em cada uma.

    ``dry_run`` apenas informa o que seria feito, sem gravar nada.
    """
    sincronizar_rotinas()
    resultados = []
    for rotina in rotinas_devidas(agora):
        if somente and rotina.nome != somente:
            continue
        funcao = ROTINAS.get(rotina.nome, (None, None, None))[2]
        if funcao is None:
            continue
        simulado = dry_run or rotina.executa_dry_run
        inicio = time.monotonic()
        try:
            detalhe = funcao(simulado)
            situacao = RotinaAgendada.Situacao.OK
            erro = ""
        except Exception as excecao:
            detalhe, situacao, erro = (
                str(excecao)[:400],
                RotinaAgendada.Situacao.FALHOU,
                str(excecao),
            )
            logger.error("rotina %s falhou: %s", rotina.nome, excecao)
        duracao = int((time.monotonic() - inicio) * 1000)
        resultados.append(
            {
                "rotina": rotina.nome,
                "situacao": situacao,
                "detalhe": detalhe,
                "simulado": simulado,
                "duracao_ms": duracao,
                "erro": erro,
            }
        )
        if not dry_run and not simulado:
            rotina.ultima_execucao = timezone.now()
            rotina.ultima_situacao = situacao
            rotina.ultimo_resultado = detalhe
            rotina.duracao_ms = duracao
            rotina.save(
                update_fields=[
                    "ultima_execucao",
                    "ultima_situacao",
                    "ultimo_resultado",
                    "duracao_ms",
                ]
            )
    return {
        "dry_run": dry_run,
        "executadas": resultados,
        "falhas": [
            item for item in resultados if item["situacao"] == RotinaAgendada.Situacao.FALHOU
        ],
    }
