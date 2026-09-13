"""Lista todas as rotas resolvidas do projeto. Importe com manage.py shell -c "import scripts.listar_rotas"."""
from __future__ import annotations

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
print("=== ROTAS:", len(rotas), "===")
print("\n".join(rotas))
