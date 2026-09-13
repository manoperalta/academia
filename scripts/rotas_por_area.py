"""Agrupa as rotas resolvidas por area (o que existe hoje no painel)."""

from __future__ import annotations

from collections import defaultdict

from django.urls import URLPattern, URLResolver, get_resolver


def percorrer(padroes, prefixo=""):
    for padrao in padroes:
        if isinstance(padrao, URLResolver):
            namespace = padrao.namespace or ""
            yield from percorrer(
                padrao.url_patterns, f"{prefixo}{namespace}:" if namespace else prefixo
            )
        elif isinstance(padrao, URLPattern) and padrao.name:
            yield f"{prefixo}{padrao.name}"


rotas = sorted(set(percorrer(get_resolver().url_patterns)))
por_area: dict[str, list[str]] = defaultdict(list)
for rota in rotas:
    area = rota.split(":")[0] if ":" in rota else "(raiz)"
    por_area[area].append(rota.split(":")[-1])

print("=== TOTAL:", len(rotas))
for area in sorted(por_area, key=lambda nome: (-len(por_area[nome]), nome)):
    nomes = sorted(por_area[area])
    print(f"[{area}] ({len(nomes)}): {' '.join(nomes)}")
