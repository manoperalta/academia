#!/usr/bin/env python3
"""Converte os modelos existentes para o nucleo de tenancy (roda no host, sem Django).

O que faz, por arquivo de modelos:

1. troca a base ``models.Model`` por ``TenantModel`` nas classes listadas;
2. insere ``from core.models import TenantModel``;
3. reescreve as travas de "instancia unica" para "unica por academia";
4. confere se nenhum modelo ja tem campos ``rede``/``unidade``/``arquivado_em``.

Idempotente: rodar duas vezes nao altera nada. Salva cada arquivo alterado com
o sufixo ``.orig`` (na primeira execucao) para conferencia.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

# app -> classes que passam a pertencer a uma rede
CONVERSAO = {
    "academia": ["Configuracao", "IdentidadeVisual"],
    "usuarios": ["Usuario", "FichaSaude"],
    "professores": ["Professor"],
    "aulas": ["Aulas", "ImagemAula"],
    "painel": ["Painel", "PainelItem"],
    "agendamento": ["Agendamento"],
    "financeiro": ["GatewayConfig", "Plano", "Pagamento", "Despesa"],
    "notificacoes": ["ConfiguracaoEmail", "ConfiguracaoWhatsapp", "Notificacao"],
}

# modelos que hoje aceitam UMA instancia na instalacao inteira
SINGLETONS = {
    "ConfiguracaoEmail": "ConfiguracaoEmail",
    "ConfiguracaoWhatsapp": "ConfiguracaoWhatsapp",
    "GatewayConfig": "GatewayConfig",
}

CAMPOS_RESERVADOS = {"rede", "unidade", "arquivado_em"}


def converte_classe(texto: str, classe: str) -> tuple[str, bool]:
    padrao = re.compile(rf"^class {classe}\(models\.Model\):", re.M)
    novo, n = padrao.subn(f"class {classe}(TenantModel):", texto)
    return novo, bool(n)


def garante_import(texto: str) -> tuple[str, bool]:
    if "from core.models import TenantModel" in texto:
        return texto, False
    linhas = texto.splitlines()
    ultima = -1
    for i, linha in enumerate(linhas):
        if linha.startswith(("import ", "from ")):
            ultima = i
    if ultima == -1:
        return texto, False
    linhas.insert(ultima + 1, "from core.models import TenantModel")
    return "\n".join(linhas) + "\n", True


def converte_trava(texto: str, modelo: str) -> tuple[str, bool]:
    padrao = re.compile(
        r"    def save\(self, \*args, \*\*kwargs\):\n"
        rf"        if not self\.pk and {modelo}\.objects\.exists\(\):\n"
        r"(            raise ValidationError\([^\n]+\)\n)"
        r"(        return super\([^\n]*\.save\(\*args, \*\*kwargs\)\))",
        re.M,
    )

    def troca(match):
        erro = match.group(1).rstrip("\n")
        return (
            "    def save(self, *args, **kwargs):\n"
            "        if not self.pk:\n"
            "            from core.context import rede_atual\n"
            "\n"
            "            rede = self.rede or rede_atual()\n"
            f"            if {modelo}.objects.filter(rede=rede).exists():\n"
            f"{erro}\n"
            "        return super().save(*args, **kwargs)"
        )

    novo, n = padrao.subn(troca, texto)
    return novo, bool(n)


def confere_campos(texto: str, classe: str) -> list[str]:
    bloco = re.search(rf"^class {classe}\(.*?\):(.*?)(?=^class |\Z)", texto, re.M | re.S)
    if not bloco:
        return []
    achados = []
    for campo in CAMPOS_RESERVADOS:
        if re.search(rf"^    {campo} = models\.", bloco.group(1), re.M):
            achados.append(campo)
    return achados


def main() -> int:
    alterados = 0
    problemas: list[str] = []
    for app, classes in CONVERSAO.items():
        caminho = RAIZ / app / "models.py"
        if not caminho.exists():
            problemas.append(f"{app}/models.py nao encontrado")
            continue
        original = texto = caminho.read_text(encoding="utf-8")
        mudancas = []

        for classe in classes:
            texto, ok = converte_classe(texto, classe)
            if ok:
                mudancas.append(f"{classe} -> TenantModel")
            conflito = confere_campos(original, classe)
            if conflito:
                problemas.append(f"{app}.{classe}: ja possui {conflito} (revisar a mao)")

        for modelo in SINGLETONS:
            texto, ok = converte_trava(texto, modelo)
            if ok:
                mudancas.append(f"{modelo}: trava unica -> unica por academia")

        if mudancas:
            texto, _ = garante_import(texto)
            if not (caminho.with_suffix(".py.orig")).exists():
                caminho.with_suffix(".py.orig").write_text(original, encoding="utf-8")
            caminho.write_text(texto, encoding="utf-8")
            alterados += 1
            print(f"[{app}/models.py]")
            for m in mudancas:
                print(f"   - {m}")

    # rotas da API no urls do projeto
    urls = RAIZ / "app" / "urls.py"
    texto = urls.read_text(encoding="utf-8")
    if "include('api.urls')" not in texto and 'include("api.urls")' not in texto:
        texto = texto.replace(
            "    path('admin/', admin.site.urls),",
            "    path('admin/', admin.site.urls),\n    path('api/', include('api.urls')),",
        )
        urls.write_text(texto, encoding="utf-8")
        alterados += 1
        print("[app/urls.py] rota /api/ adicionada")

    print(f"\n{alterados} arquivo(s) alterado(s)")
    if problemas:
        print("\nATENCAO:")
        for p in problemas:
            print(f"   ! {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
