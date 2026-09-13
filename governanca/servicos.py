"""Servicos de governanca: dominio, midia, backup, observabilidade e LGPD."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
import secrets
import shutil
import socket
import subprocess
import zipfile
from datetime import timedelta
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.core.cache import cache
from django.core.serializers.json import DjangoJSONEncoder
from django.db import connection, transaction
from django.utils import timezone

from core.models import Rede, StatusCertificado, StatusDominio
from core.seguranca import prefixo_de_midia
from governanca.models import (
    AcessoDadoSensivel,
    ErroTenant,
    MetricaTenant,
    RegistroBackup,
    RegraRetencao,
    SolicitacaoTitular,
    TentativaDeLogin,
)

logger = logging.getLogger("governanca")

LIMITE_DIARIOS = 7
LIMITE_SEMANAIS = 4
DIAS_DE_RETENCAO = 30
TEMPO_LIMITE_HTTP = 8
LIMIAR_ALERTA_5XX = 5  # por cliente em 24h
CHAVE_METRICAS = "metricas:tenant:{rede}:{hora}"


# ==================================================================== PROPAGACAO / DOMINIO
def dominio_base() -> str:
    """Dominio onde vive o subdominio de cada cliente."""
    from plataforma.models import ConfiguracaoPlataforma

    return (
        getattr(ConfiguracaoPlataforma.obter(), "dominio_base", "") or ""
    ).strip() or "academia.safestack.com.br"


def subdominio_da(rede) -> str:
    return f"{rede.slug}.{dominio_base()}"


def hosts_da_rede(rede) -> list[str]:
    """Todos os hosts que devem resolver para este cliente."""
    hosts = [subdominio_da(rede)]
    if rede.dominio:
        hosts.append(rede.dominio.strip().lower())
    return hosts


def rede_por_host(host: str, porta: str | None = None):
    """Encontra o cliente pelo Host da requisicao (subdominio ou dominio proprio)."""
    nome = (host or "").split(":")[0].strip().lower()
    if not nome:
        return None
    if nome.endswith(dominio_base()):
        prefixo = nome[: -(len(dominio_base()) + 1)].split(".")[-1]
        if prefixo:
            return Rede.todos.filter(slug=prefixo).first()
    return Rede.todos.filter(dominio__iexact=nome).first()


def token_de_verificacao(rede) -> str:
    if not rede.dominio_token:
        rede.dominio_token = secrets.token_urlsafe(24)
        rede.save(update_fields=["dominio_token", "atualizado_em"])
    return rede.dominio_token


def instrucoes_de_dns(rede) -> dict:
    """O que o cliente precisa criar no DNS dele (RF-PLT-051)."""
    token = token_de_verificacao(rede)
    return {
        "host": rede.dominio or "",
        "registros": [
            {
                "tipo": "A",
                "nome": rede.dominio or "@",
                "valor": _endereco_publico(),
                "para": "apontar o dominio para o servidor da SafeStack",
            },
            {
                "tipo": "TXT",
                "nome": f"_academia-verificacao.{rede.dominio}" if rede.dominio else "",
                "valor": f"academia-verificacao={token}",
                "para": "comprovar que o dominio e seu",
            },
            {
                "tipo": "CNAME",
                "nome": f"www.{rede.dominio}" if rede.dominio else "www",
                "valor": subdominio_da(rede),
                "para": "opcional: atender tambem o www",
            },
        ],
        "arquivo_de_teste": {
            "caminho": "/.well-known/academia-verificacao.txt",
            "conteudo": token,
            "para": "alternativa ao TXT: publique este arquivo no dominio",
        },
    }


def _endereco_publico() -> str:
    try:
        return socket.gethostbyname(dominio_base())
    except OSError:
        return "(endereco do servidor)"


def _checar_arquivo_no_dominio(dominio: str, token: str) -> tuple[bool, str]:
    """Verifica por HTTP: /.well-known/academia-verificacao.txt precisa conter o token."""
    try:
        import requests
    except ImportError:  # pragma: no cover - requests e dependencia do gateway
        return False, "nao consegui verificar por HTTP agora; publique o arquivo e tente de novo"
    for esquema in ("http", "https"):
        try:
            resposta = requests.get(
                f"{esquema}://{dominio}/.well-known/academia-verificacao.txt",
                timeout=TEMPO_LIMITE_HTTP,
                allow_redirects=True,
            )
        except Exception:
            continue
        if resposta.status_code == 200 and token.strip() in resposta.text:
            return True, f"token encontrado em {esquema}://{dominio}"
    return False, (
        "nao encontrei o arquivo de verificacao no dominio. Publique o conteudo do "
        "token em /.well-known/academia-verificacao.txt"
    )


def _checar_txt(dominio: str, token: str) -> tuple[bool, str]:
    """Verifica por DNS (TXT) quando a biblioteca dnspython estiver disponivel."""
    try:
        import dns.resolver  # type: ignore[import-not-found]
    except ImportError:
        return False, "verificacao por DNS indisponivel nesta instalacao (use o arquivo de texto)"
    try:
        respostas = dns.resolver.resolve(f"_academia-verificacao.{dominio}", "TXT", lifetime=6)
    except Exception:
        return False, "nao encontrei o registro TXT _academia-verificacao"
    for item in respostas:
        texto = (
            b"".join(item.strings).decode("utf-8", errors="replace")
            if hasattr(item, "strings")
            else str(item)
        )
        if token in texto:
            return True, "registro TXT confirmado"
    return False, "o registro TXT existe, mas com valor diferente do token"


def verificar_dominio(rede, forcar: bool = False) -> dict:
    """Confere o dominio proprio e atualiza o estado (RF-PLT-051/052)."""
    if not rede.dominio:
        rede.dominio_status = StatusDominio.NAO_CONFIGURADO
        rede.dominio_diagnostico = "sem dominio proprio configurado"
        rede.save(update_fields=["dominio_status", "dominio_diagnostico", "atualizado_em"])
        return {
            "ok": False,
            "mensagem": "Sem dominio proprio configurado.",
            "status": rede.dominio_status,
        }

    if not forcar and rede.dominio_status == StatusDominio.PRONTO:
        return {"ok": True, "mensagem": "Dominio verificado.", "status": rede.dominio_status}

    token = token_de_verificacao(rede)
    rede.dominio_status = StatusDominio.VERIFICANDO
    rede.dominio_tentativas = (rede.dominio_tentativas or 0) + 1
    rede.save(update_fields=["dominio_status", "dominio_tentativas", "atualizado_em"])

    achou_txt, mensagem_txt = _checar_txt(rede.dominio, token)
    if achou_txt:
        confere, mensagem = True, mensagem_txt or "registro TXT confirmado"
    else:
        confere, mensagem = _checar_arquivo_no_dominio(rede.dominio, token)

    if confere:
        rede.dominio_status = StatusDominio.PRONTO
        rede.dominio_verificado_em = timezone.now()
        rede.dominio_diagnostico = "dominio verificado; emitindo certificado"
        rede.certificado_status = StatusCertificado.EMITINDO
        rede.certificado_erro = ""
    else:
        rede.dominio_status = StatusDominio.PENDENTE_DNS
        rede.dominio_diagnostico = mensagem
    rede.save(
        update_fields=[
            "dominio_status",
            "dominio_verificado_em",
            "dominio_diagnostico",
            "certificado_status",
            "certificado_erro",
            "atualizado_em",
        ]
    )
    return {
        "ok": confere,
        "mensagem": mensagem,
        "status": rede.dominio_status,
        "instrucoes": instrucoes_de_dns(rede),
    }


def config_do_router(rede) -> str:
    """Trecho de configuracao do proxy para atender o dominio deste cliente (com TLS)."""
    hosts = hosts_da_rede(rede)
    regras = " || ".join(f"Host(`{host}`)" for host in hosts)
    return (
        f"# {rede.nome} (rede #{rede.pk}) -- gerado em {timezone.now():%d/%m/%Y %H:%M}\n"
        f"http:\n"
        f"  routers:\n"
        f"    tenant-{rede.pk}:\n"
        f'      rule: "{regras}"\n'
        f"      entryPoints: [websecure]\n"
        f"      service: tenant-{rede.pk}\n"
        f"      tls:\n"
        f"        certResolver: letsencrypt\n"
        f"        domains:\n"
        + "".join(f"          - main: {host}\n" for host in hosts)
        + f"  services:\n"
        f"    tenant-{rede.pk}:\n"
        f"      loadBalancer:\n"
        f"        servers:\n"
        f'          - url: "http://{rede.slug}-web:8000"\n'
    )


def estado_do_provisionamento(rede) -> dict:
    """Diagnostico em linguagem de cliente (RF-PLT-052)."""
    passos = [
        {
            "nome": "Endereco do painel",
            "situacao": "pronto",
            "detalhe": f"https://{subdominio_da(rede)}/gestao/",
        }
    ]
    if not rede.dominio:
        passos.append(
            {
                "nome": "Dominio proprio",
                "situacao": "opcional",
                "detalhe": "Voce pode usar o dominio da SafeStack ou trazer o seu.",
            }
        )
    else:
        if rede.dominio_status == StatusDominio.PRONTO:
            situacao = "pronto"
            detalhe = "Dominio verificado."
        elif rede.dominio_status == StatusDominio.PENDENTE_DNS:
            situacao = "aguardando"
            detalhe = "Aguardando propagacao do DNS. Isso costuma levar de minutos a algumas horas."
        elif rede.dominio_status == StatusDominio.ERRO:
            situacao = "erro"
            detalhe = rede.dominio_diagnostico or "Nao conseguimos verificar o dominio."
        else:
            situacao = "pendente"
            detalhe = rede.dominio_diagnostico or "Ainda nao verificamos o dominio."
        passos.append({"nome": "Dominio proprio", "situacao": situacao, "detalhe": detalhe})

        certificado = rede.certificado_status
        if certificado == StatusCertificado.EMITIDO:
            passos.append(
                {
                    "nome": "Certificado (cadeado)",
                    "situacao": "pronto",
                    "detalhe": f"Emitido em {rede.certificado_emitido_em:%d/%m/%Y}."
                    if rede.certificado_emitido_em
                    else "Emitido.",
                }
            )
        elif certificado == StatusCertificado.ERRO:
            passos.append(
                {
                    "nome": "Certificado (cadeado)",
                    "situacao": "erro",
                    "detalhe": rede.certificado_erro
                    or "Falha ao emitir o certificado. Vamos reemitir automaticamente.",
                }
            )
        else:
            passos.append(
                {
                    "nome": "Certificado (cadeado)",
                    "situacao": "aguardando",
                    "detalhe": "Emitimos assim que o DNS estiver apontando.",
                }
            )

    pronto = all(passo["situacao"] in {"pronto", "opcional"} for passo in passos)
    return {
        "pronto": pronto,
        "resumo": "Tudo pronto."
        if pronto
        else "Ainda falta um passo para o seu endereco funcionar.",
        "passos": passos,
        "hosts": hosts_da_rede(rede),
        "certificado": rede.get_certificado_status_display(),
    }


def reemitir_certificado(rede) -> dict:
    """Marca o certificado para reemissao (o Traefik nao repete o pedido sozinho apos erro)."""
    if rede.dominio_status != StatusDominio.PRONTO:
        return {"ok": False, "mensagem": "Confirme o DNS do dominio antes de emitir o certificado."}
    rede.certificado_status = StatusCertificado.EMITINDO
    rede.certificado_erro = ""
    rede.save(update_fields=["certificado_status", "certificado_erro", "atualizado_em"])
    return {
        "ok": True,
        "mensagem": "Certificado marcado para reemissao. O proxy vai pedir de novo.",
        "config": config_do_router(rede),
    }


# ==================================================================== MIDIA (RNF-010)
def namespace_de_midia(rede) -> str:
    return f"redes/{prefixo_de_midia(rede)}"


def mover_midia_para_namespace(dry_run: bool = True) -> dict:
    """Traz arquivos antigos (media/<arquivo>) para o namespace do tenant (RNF-010)."""
    raiz = Path(settings.MEDIA_ROOT)
    if not raiz.exists():
        return {"movidos": 0, "ignorados": 0, "detalhes": [], "dry_run": dry_run}
    movidos, ignorados, detalhes = 0, 0, []
    for arquivo in sorted(p for p in raiz.rglob("*") if p.is_file()):
        relativo = arquivo.relative_to(raiz).as_posix()
        if relativo.startswith("redes/"):
            ignorados += 1
            continue
        dono = _rede_pelo_conteudo(relativo)
        if dono is None:
            ignorados += 1
            detalhes.append(f"sem dono identificado: {relativo}")
            continue
        destino_relativo = f"{namespace_de_midia(dono)}/{relativo}"
        detalhes.append(f"{relativo} -> {destino_relativo}")
        if not dry_run:
            destino = raiz / destino_relativo
            destino.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(arquivo), str(destino))
            _reescrever_caminhos(relativo, destino_relativo)
        movidos += 1
    return {"movidos": movidos, "ignorados": ignorados, "detalhes": detalhes, "dry_run": dry_run}


def _rede_pelo_conteudo(relativo: str):
    """Descobre de quem e o arquivo procurando o caminho em qualquer campo de arquivo."""
    for modelo in apps.get_models():
        campos = [
            campo
            for campo in modelo._meta.get_fields()
            if getattr(campo, "get_internal_type", lambda: "")() in {"FileField", "ImageField"}
        ]
        if not campos:
            continue
        for campo in campos:
            filtro = {campo.name: relativo}
            registro = modelo._default_manager.filter(**filtro).select_related("rede").first()
            if registro is not None and getattr(registro, "rede", None) is not None:
                return registro.rede
    return None


def _reescrever_caminhos(antigo: str, novo: str) -> int:
    """Atualiza no banco os caminhos dos arquivos movidos."""
    atualizados = 0
    for modelo in apps.get_models():
        campos = [
            campo
            for campo in modelo._meta.get_fields()
            if getattr(campo, "get_internal_type", lambda: "")() in {"FileField", "ImageField"}
        ]
        for campo in campos:
            atualizados += modelo._default_manager.filter(**{campo.name: antigo}).update(
                **{campo.name: novo}
            )
    return atualizados


def montar_url_de_midia(caminho: str) -> str:
    """URL protegida (sessao do tenant) para um arquivo de midia."""
    from django.urls import reverse

    if not caminho:
        return ""
    return reverse("governanca:midia", args=[caminho])


# ==================================================================== BACKUP (RNF-005)
def pasta_de_backup() -> Path:
    destino = Path(getattr(settings, "BACKUP_DIR", Path(settings.BASE_DIR) / "backups"))
    destino.mkdir(parents=True, exist_ok=True)
    return destino


def _sha256(caminho: Path) -> str:
    resumo = hashlib.sha256()
    with caminho.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            resumo.update(bloco)
    return resumo.hexdigest()


def _dump_logico() -> bytes:
    """Backup logico de todas as linhas (funciona em qualquer ambiente e e testavel)."""
    from django.core import serializers

    partes = []
    for modelo in apps.get_models():
        if modelo._meta.proxy or modelo._meta.abstract:
            continue
        try:
            dados = serializers.serialize("json", modelo._default_manager.all())
        except Exception:
            continue
        partes.append(dados)
    return (
        "[" + ",".join(parte.strip("[]") for parte in partes if parte.strip("[]")) + "]"
    ).encode()


def _dump_com_pg_dump() -> bytes:
    comando = ["pg_dump", "--no-owner", "--no-acl", "--clean", "--if-exists"]
    if connection.settings_dict.get("NAME"):
        comando.append(str(connection.settings_dict["NAME"]))
    return subprocess.check_output(comando, env=_ambiente_do_banco(), timeout=900)


def _ambiente_do_banco() -> dict:
    import os

    ambiente = os.environ.copy()
    configuracao = connection.settings_dict
    for chave, valor in (
        ("PGHOST", configuracao.get("HOST")),
        ("PGPORT", configuracao.get("PORT")),
        ("PGUSER", configuracao.get("USER")),
        ("PGPASSWORD", configuracao.get("PASSWORD")),
    ):
        if valor:
            ambiente[chave] = str(valor)
    return ambiente


def executar_backup(metodo: str = "auto", agora=None) -> RegistroBackup:
    """Faz o backup do banco, grava o arquivo, o hash e o registro (RNF-005)."""
    agora = agora or timezone.now()
    destino = pasta_de_backup()
    nome = f"banco-{agora:%Y%m%d-%H%M%S}.json.gz"
    caminho = destino / nome
    registro = RegistroBackup.objects.create(
        arquivo=str(caminho),
        tipo=RegistroBackup.Tipo.BANCO,
        retencao_ate=(agora + timedelta(days=DIAS_DE_RETENCAO)).date(),
    )
    try:
        if metodo == "pg_dump" or (metodo == "auto" and shutil.which("pg_dump")):
            conteudo = _dump_com_pg_dump()
        else:
            import gzip

            conteudo = gzip.compress(_dump_logico())
        caminho.write_bytes(conteudo)
        registro.tamanho_bytes = len(conteudo)
        registro.sha256 = _sha256(caminho)
        registro.situacao = RegistroBackup.Situacao.OK
        registro.save(update_fields=["tamanho_bytes", "sha256", "situacao"])
    except Exception as erro:
        registro.situacao = RegistroBackup.Situacao.FALHOU
        registro.erro = str(erro)[:2000]
        registro.save(update_fields=["situacao", "erro"])
        logger.error("falha no backup: %s", erro)
    return registro


def verificar_backup(registro: RegistroBackup | None = None) -> dict:
    """Restauracao de teste: confere arquivo, hash e conteudo legivel (RNF-005)."""
    registro = (
        registro
        or RegistroBackup.objects.filter(tipo=RegistroBackup.Tipo.BANCO)
        .order_by("-criado_em")
        .first()
    )
    if registro is None:
        return {"ok": False, "detalhe": "nenhum backup registrado"}
    caminho = Path(registro.arquivo)
    problemas = []
    if not caminho.exists():
        problemas.append("arquivo nao encontrado no disco")
    else:
        if registro.sha256 and _sha256(caminho) != registro.sha256:
            problemas.append("hash diferente do registrado (arquivo corrompido ou alterado)")
        if caminho.stat().st_size == 0:
            problemas.append("arquivo vazio")
        conteudo = caminho.read_bytes()
        try:
            import gzip

            if conteudo[:2] == b"\x1f\x8b":
                conteudo = gzip.decompress(conteudo)
            if conteudo.strip().startswith(b"["):
                linhas = len(json.loads(conteudo))
                registro.verificacao = f"backup logico legivel com {linhas} registros"
            else:
                registro.verificacao = f"dump SQL legivel ({len(conteudo)} bytes)"
        except Exception as erro:
            problemas.append(f"nao consegui ler o conteudo: {erro}")
    registro.verificado_em = timezone.now()
    registro.verificacao = "; ".join(problemas) if problemas else registro.verificacao
    registro.save(update_fields=["verificado_em", "verificacao"])
    return {"ok": not problemas, "detalhe": registro.verificacao or "ok", "registro": registro}


def exportar_tenant(rede) -> RegistroBackup:
    """Restauracao pontual: exporta TODOS os dados de um cliente (RNF-005/RF-TEN-021)."""
    agora = timezone.now()
    destino = pasta_de_backup()
    caminho = destino / f"tenant-{rede.slug}-{agora:%Y%m%d-%H%M%S}.json"
    registro = RegistroBackup.objects.create(
        arquivo=str(caminho),
        tipo=RegistroBackup.Tipo.TENANT,
        rede=rede,
        retencao_ate=(agora + timedelta(days=DIAS_DE_RETENCAO)).date(),
    )
    try:
        dados = _dados_do_tenant(rede)
        caminho.write_bytes(
            json.dumps(dados, cls=DjangoJSONEncoder, ensure_ascii=False, indent=2).encode()
        )
        registro.tamanho_bytes = caminho.stat().st_size
        registro.sha256 = _sha256(caminho)
        registro.situacao = RegistroBackup.Situacao.OK
        registro.save(update_fields=["tamanho_bytes", "sha256", "situacao"])
    except Exception as erro:
        registro.situacao = RegistroBackup.Situacao.FALHOU
        registro.erro = str(erro)[:2000]
        registro.save(update_fields=["situacao", "erro"])
    return registro


def _modelos_com_rede() -> list:
    modelos = []
    for modelo in apps.get_models():
        if modelo._meta.proxy or modelo._meta.abstract:
            continue
        if any(campo.name == "rede" for campo in modelo._meta.get_fields()):
            modelos.append(modelo)
    return modelos


def _dados_do_tenant(rede) -> dict:
    dados = {
        "rede": {
            "nome": rede.nome,
            "slug": rede.slug,
            "cnpj": rede.cnpj,
            "criado_em": rede.criado_em,
        },
        "exportado_em": timezone.now(),
        "tabelas": {},
    }
    for modelo in _modelos_com_rede():
        registros = list(modelo._default_manager.filter(rede=rede).values())
        chave = f"{modelo._meta.app_label}.{modelo._meta.model_name}"
        dados["tabelas"][chave] = registros
    return dados


def aplicar_retencao_de_backups(dry_run: bool = True) -> dict:
    """Mantem 7 diarios + 4 semanais e apaga o resto (RNF-005)."""
    backups = list(
        RegistroBackup.objects.filter(situacao=RegistroBackup.Situacao.OK).order_by("-criado_em")
    )
    hoje = timezone.now().date()
    recentes = [b for b in backups if (hoje - b.criado_em.date()).days <= LIMITE_DIARIOS]
    antigos = [b for b in backups if b not in recentes]
    semanais, descartar = [], []
    for backup in antigos:
        if backup.criado_em.weekday() == 6 and len(semanais) < LIMITE_SEMANAIS:
            semanais.append(backup)
        else:
            descartar.append(backup)
    remover = [b for b in descartar if not b.verificado or b not in semanais]
    detalhes = [f"apagar {Path(b.arquivo).name}" for b in remover]
    if not dry_run:
        for backup in remover:
            caminho = Path(backup.arquivo)
            caminho.unlink(missing_ok=True)
            backup.delete()
    return {
        "mantidos": len(recentes) + len(semanais),
        "apagados": 0 if dry_run else len(remover),
        "detalhes": detalhes,
        "dry_run": dry_run,
    }


def prazo_do_pedido(hoje=None):
    """Prazo legal para responder um pedido de titular (LGPD: 15 dias)."""
    return (hoje or timezone.localdate()) + timedelta(days=SolicitacaoTitular.PRAZO_LEGAL_DIAS)


# ==================================================================== OBSERVABILIDADE (RNF-008)
def _hora_cheia(inicio=None):
    agora = inicio or timezone.now()
    return agora.replace(minute=0, second=0, microsecond=0)


def registrar_requisicao(rede, status_code: int, duracao_ms: int) -> None:
    """Conta a requisicao no cache; a agregacao horaria persiste no banco."""
    chave = CHAVE_METRICAS.format(rede=rede.pk if rede else 0, hora=_hora_cheia().timestamp())
    dados = cache.get(
        chave,
        {"requisicoes": 0, "erros_5xx": 0, "erros_4xx": 0, "tempo_total_ms": 0, "tempo_max_ms": 0},
    )
    dados["requisicoes"] += 1
    dados["tempo_total_ms"] += duracao_ms
    dados["tempo_max_ms"] = max(dados["tempo_max_ms"], duracao_ms)
    if status_code >= 500:
        dados["erros_5xx"] += 1
    elif status_code >= 400:
        dados["erros_4xx"] += 1
    cache.set(chave, dados, 3 * 3600)


def agregar_metricas(quando=None) -> int:
    """Persiste no banco as metricas acumuladas no cache."""
    quando = _hora_cheia(quando)
    gravadas = 0
    from django.core.cache import cache as _cache

    for rede in [*Rede.todos.all(), None]:
        chave = CHAVE_METRICAS.format(rede=rede.pk if rede else 0, hora=quando.timestamp())
        dados = _cache.get(chave)
        if not dados or not dados["requisicoes"]:
            continue
        MetricaTenant.objects.update_or_create(
            rede=rede,
            inicio=quando,
            defaults={
                "requisicoes": dados["requisicoes"],
                "erros_5xx": dados["erros_5xx"],
                "erros_4xx": dados["erros_4xx"],
                "tempo_total_ms": dados["tempo_total_ms"],
                "tempo_max_ms": dados["tempo_max_ms"],
            },
        )
        _cache.delete(chave)
        gravadas += 1
    return gravadas


def registrar_erro(
    rede,
    rota: str,
    metodo: str,
    status: int,
    tipo: str = "",
    mensagem: str = "",
    traceback_curto: str = "",
    usuario=None,
) -> ErroTenant | None:
    """Guarda o erro 5xx do cliente, sem deixar o mesmo erro inundar a lista."""
    chave = f"erro:{rede.pk if rede else 0}:{rota[:60]}:{tipo[:40]}"
    if cache.get(chave):
        return None
    cache.set(chave, 1, 300)
    return ErroTenant.objects.create(
        rede=rede,
        rota=rota[:200],
        metodo=metodo[:10],
        status=status,
        tipo=tipo[:120],
        mensagem=mensagem[:2000],
        traceback_curto=traceback_curto[-4000:],
        usuario=usuario if getattr(usuario, "pk", None) else None,
    )


def resumo_de_saude(horas: int = 24) -> dict:
    """Painel de saude por cliente (RF-PLT-006/RNF-008)."""
    desde = timezone.now() - timedelta(hours=horas)
    linhas = []
    for rede in Rede.todos.all():
        metricas = MetricaTenant.objects.filter(rede=rede, inicio__gte=desde)
        requisicoes = sum(m.requisicoes for m in metricas)
        erros = sum(m.erros_5xx for m in metricas)
        tempo_medio = (sum(m.tempo_total_ms for m in metricas) / requisicoes) if requisicoes else 0
        ultimo_erro = ErroTenant.objects.filter(rede=rede).order_by("-criado_em").first()
        linhas.append(
            {
                "rede": rede,
                "requisicoes": requisicoes,
                "erros_5xx": erros,
                "tempo_medio_ms": int(tempo_medio),
                "ultimo_erro": ultimo_erro,
                "alerta": erros >= LIMIAR_ALERTA_5XX,
            }
        )
    return {
        "linhas": sorted(linhas, key=lambda linha: linha["erros_5xx"], reverse=True),
        "horas": horas,
        "sem_metricas": not any(linha["requisicoes"] for linha in linhas),
    }


def alertas_pendentes() -> list[str]:
    """Alertas simples para a equipe (RNF-008): 5xx, backup e prazos LGPD."""
    alertas = []
    saude = resumo_de_saude()
    for linha in saude["linhas"]:
        if linha["alerta"]:
            alertas.append(
                f"{linha['rede'].nome}: {linha['erros_5xx']} erros 5xx em {saude['horas']}h"
            )

    ultimo = (
        RegistroBackup.objects.filter(tipo=RegistroBackup.Tipo.BANCO).order_by("-criado_em").first()
    )
    if ultimo is None:
        alertas.append("nenhum backup do banco registrado")
    elif ultimo.situacao == RegistroBackup.Situacao.FALHOU:
        alertas.append(f"backup falhou em {ultimo.criado_em:%d/%m %H:%M}: {ultimo.erro[:120]}")
    elif not ultimo.verificado:
        alertas.append("backup mais recente ainda nao foi verificado por restauracao de teste")
    elif (timezone.now().date() - ultimo.criado_em.date()).days > 1:
        alertas.append(f"ultimo backup tem {ultimo.criado_em:%d/%m} (mais de 1 dia)")

    atrasadas = list(SolicitacaoTitular.objects.filter(situacao=SolicitacaoTitular.Situacao.ABERTA))
    vencidas = [s for s in atrasadas if s.atrasada]
    if vencidas:
        alertas.append(f"{len(vencidas)} solicitacao(oes) de titular com prazo vencido")
    return alertas


# ==================================================================== LGPD (RNF-006 / RF-TEN-021)
def _campos_existentes(modelo, desejados):
    """Filtra os campos que realmente existem no modelo (varios clientes tem esquemas antigos)."""
    nomes = {campo.name for campo in modelo._meta.get_fields()}
    return [nome for nome in desejados if nome in nomes]


def _usuario_do_titular(aluno):
    """Perfil do aluno e o usuario de login, quando existir."""
    usuario = getattr(aluno, "user", None)
    return usuario


def dados_do_titular(rede, aluno) -> dict:
    """Tudo que guardamos sobre a pessoa, em formato legivel (LGPD art. 18)."""
    from agendamento.models import Agendamento
    from financeiro.models import Pagamento

    usuario = _usuario_do_titular(aluno)
    dados = {
        "gerado_em": timezone.now(),
        "academia": {"nome": rede.nome, "cnpj": rede.cnpj},
        "cadastro": {
            "nome": aluno.nome,
            "email": getattr(aluno, "email_user", ""),
            "telefone": getattr(aluno, "telefone_user", ""),
            "cpf": getattr(aluno, "cpf_cnpj_user", ""),
            "nascimento": getattr(aluno, "data_nasc", None),
            "endereco": getattr(aluno, "endereco_user", ""),
            "status": getattr(aluno, "status_user", ""),
            "criado_em": getattr(aluno, "criado_em", None),
            "tem_login": usuario is not None,
        },
        "pagamentos": [],
        "agendamentos": [],
        "ficha_saude": None,
    }
    if usuario is not None:
        campos_pagamento = _campos_existentes(
            Pagamento,
            [
                "id",
                "valor",
                "data_pagamento",
                "data_inicio",
                "data_fim",
                "status",
                "plano",
                "link_pagamento",
            ],
        )
        dados["pagamentos"] = list(
            Pagamento.objects.filter(usuario=usuario, rede=rede).values(*campos_pagamento)
        )
        campos_agendamento = _campos_existentes(
            Agendamento, ["id", "data_agendamento", "status", "painel"]
        )
        dados["agendamentos"] = list(
            Agendamento.objects.filter(aluno=usuario, rede=rede).values(*campos_agendamento)
        )
        ficha = _ficha_do_aluno(aluno)
        if ficha is not None:
            campos_ficha = _campos_existentes(
                type(ficha),
                [
                    "peso",
                    "altura",
                    "restricoes",
                    "prescricoes",
                    "obs",
                    "usa_medicamento",
                    "qual_medicamento",
                ],
            )
            dados["ficha_saude"] = {campo: getattr(ficha, campo) for campo in campos_ficha}
    return dados


def _ficha_do_aluno(aluno):
    try:
        from usuarios.models import FichaSaude

        return FichaSaude.todos.filter(usuario=aluno).first()
    except Exception:
        return None


def exportar_titular_zip(rede, aluno) -> bytes:
    """ZIP com os dados do titular (JSON + CSV) para entregar ao proprio titular."""
    dados = dados_do_titular(rede, aluno)
    memoria = io.BytesIO()
    with zipfile.ZipFile(memoria, "w", zipfile.ZIP_DEFLATED) as pacote:
        pacote.writestr(
            "dados.json", json.dumps(dados, cls=DjangoJSONEncoder, ensure_ascii=False, indent=2)
        )
        pacote.writestr(
            "leia-me.txt",
            (
                "Este pacote conteudo os dados que a academia guarda sobre voce.\n"
                "dados.json  -> cadastro, pagamentos, agendamentos e ficha de saude\n"
                "pagamentos.csv -> a mesma lista de pagamentos em planilha\n"
            ),
        )
        if dados["pagamentos"]:
            saida = io.StringIO()
            escritor = csv.DictWriter(saida, fieldnames=list(dados["pagamentos"][0].keys()))
            escritor.writeheader()
            escritor.writerows(dados["pagamentos"])
            pacote.writestr("pagamentos.csv", saida.getvalue())
    return memoria.getvalue()


def anonimizar_titular(rede, aluno, usuario=None, motivo: str = "") -> dict:
    """Anonimiza os dados pessoais mantendo o que a lei obriga a guardar (RF-TEN-021)."""
    marcador = f"ANONIMIZADO-{aluno.pk}"
    with transaction.atomic():
        aluno.nome = marcador
        for campo, valor in (
            ("email_user", f"{marcador.lower()}@anonimizado.local"),
            ("telefone_user", ""),
            ("cpf_cnpj_user", ""),
            ("endereco_user", ""),
            ("numero_end_user", ""),
            ("bairro_user", ""),
            ("cep_user", ""),
        ):
            if hasattr(aluno, campo):
                setattr(aluno, campo, valor)
        if hasattr(aluno, "data_nasc"):
            aluno.data_nasc = None
        if hasattr(aluno, "status_user"):
            aluno.status_user = "Inativo"
        aluno.save()
        ficha = _ficha_do_aluno(aluno)
        if ficha is not None:
            for campo in ("restricoes", "prescricoes", "obs", "qual_medicamento"):
                if hasattr(ficha, campo):
                    setattr(ficha, campo, "")
            if hasattr(ficha, "usa_medicamento"):
                ficha.usa_medicamento = False
            ficha.save()
        usuario_login = _usuario_do_titular(aluno)
        if usuario_login is not None:
            usuario_login.is_active = False
            usuario_login.email = f"{marcador.lower()}@anonimizado.local"
            if hasattr(usuario_login, "first_name"):
                usuario_login.first_name = marcador
            usuario_login.save()
    from api.auditoria import registrar

    registrar(
        "anonimizar",
        "titular",
        entidade_id=aluno.pk,
        descricao=f"Titular {marcador} anonimizado. Pagamentos preservados por obrigacao fiscal. {motivo}".strip(),
    )
    return {"ok": True, "pagamentos_preservados": True, "marcador": marcador}


def aplicar_retencao(hoje=None, dry_run: bool = True) -> dict:
    """Expurgo conforme as regras de retencao (RNF-006)."""
    hoje = hoje or timezone.localdate()
    resultado = {"regras": [], "dry_run": dry_run}
    mapa = {
        "tentativas_login": (TentativaDeLogin, "criado_em"),
        "erro_tenant": (ErroTenant, "criado_em"),
        "metrica_tenant": (MetricaTenant, "inicio"),
        "acesso_dado_sensivel": (AcessoDadoSensivel, "criado_em"),
        "solicitacao_titular": (SolicitacaoTitular, "criado_em"),
    }
    for regra in RegraRetencao.objects.filter(ativo=True):
        modelo_campo = mapa.get(regra.entidade)
        if modelo_campo is None:
            continue
        modelo, campo = modelo_campo
        limite = timezone.now() - timedelta(days=regra.prazo_dias)
        consulta = modelo.objects.filter(**{f"{campo}__lt": limite})
        quantidade = consulta.count()
        if quantidade and not dry_run and regra.acao != RegraRetencao.Acao.CONSERVAR:
            consulta.delete()
        if quantidade:
            resultado["regras"].append(
                {
                    "entidade": regra.entidade,
                    "prazo_dias": regra.prazo_dias,
                    "acao": regra.get_acao_display(),
                    "registros": quantidade,
                    "base_legal": regra.base_legal_efetiva,
                }
            )
    return resultado
