#!/usr/bin/env python3
"""Fase 5: campos de dominio/certificado/midia na Rede (core). Idempotente e verificado."""
from __future__ import annotations

from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

ENUMS = """
# Estado do dominio proprio e do subdominio (RF-PLT-052)
class StatusDominio(models.TextChoices):
    NAO_CONFIGURADO = "nao_configurado", "Sem dominio proprio"
    PENDENTE_DNS = "pendente_dns", "Aguardando DNS"
    VERIFICANDO = "verificando", "Verificando"
    PRONTO = "pronto", "Pronto"
    ERRO = "erro", "Com erro"


class StatusCertificado(models.TextChoices):
    PENDENTE = "pendente", "Pendente"
    EMITINDO = "emitindo", "Emitindo"
    EMITIDO = "emitido", "Emitido"
    ERRO = "erro", "Com erro"

"""

CAMPOS = """    dominio = models.CharField("dominio proprio", max_length=253, blank=True)
    dominio_status = models.CharField(
        "status do dominio",
        max_length=20,
        choices=StatusDominio.choices,
        default=StatusDominio.NAO_CONFIGURADO,
    )
    dominio_token = models.CharField("token de verificacao", max_length=64, blank=True)
    dominio_verificado_em = models.DateTimeField("dominio verificado em", null=True, blank=True)
    dominio_diagnostico = models.CharField("diagnostico do dominio", max_length=250, blank=True)
    dominio_tentativas = models.PositiveIntegerField("tentativas de verificacao", default=0)
    certificado_status = models.CharField(
        "status do certificado",
        max_length=20,
        choices=StatusCertificado.choices,
        default=StatusCertificado.PENDENTE,
    )
    certificado_emitido_em = models.DateTimeField("certificado emitido em", null=True, blank=True)
    certificado_erro = models.TextField("erro do certificado", blank=True)
    media_prefixo = models.CharField(
        "prefixo da midia",
        max_length=80,
        blank=True,
        help_text="Namespace dos arquivos deste cliente (padrao: o slug).",
    )"""


def main() -> None:
    alvo = RAIZ / "core" / "models.py"
    texto = alvo.read_text(encoding="utf-8")
    original = texto

    if "class StatusDominio" not in texto:
        marca = "class Rede(models.Model):"
        if marca not in texto:
            raise SystemExit("ERRO: class Rede nao encontrada")
        texto = texto.replace(marca, ENUMS.strip() + "\n\n\n" + marca, 1)

    if "dominio_status" not in texto:
        marca_campo = '    dominio = models.CharField("dominio proprio", max_length=253, blank=True)'
        if marca_campo not in texto:
            raise SystemExit("ERRO: campo dominio nao encontrado")
        texto = texto.replace(marca_campo, CAMPOS, 1)

    for obrigatorio in ("class StatusDominio", "class StatusCertificado", "dominio_status",
                        "certificado_status", "media_prefixo"):
        if obrigatorio not in texto:
            raise SystemExit(f"ERRO: faltou {obrigatorio}")

    if texto == original:
        print("core/models.py ja estava atualizado")
    else:
        alvo.write_text(texto, encoding="utf-8")
        print(f"core/models.py atualizado ({len(texto.splitlines())} linhas)")


if __name__ == "__main__":
    main()
