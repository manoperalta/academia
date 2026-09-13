"""Isola o problema: o Django serve o estatico pelo cliente de teste?"""

from __future__ import annotations

from django.test import Client

cliente = Client()
for caminho in [
    "/static/design/tokens.css",
    "/demo/static/design/tokens.css",
    "/static/admin/css/base.css",
    "/media/",
]:
    resposta = cliente.get(caminho)
    print(f"{caminho:40s} -> {resposta.status_code}")

from django.contrib.staticfiles import finders

print("finders acham:", finders.find("design/tokens.css"))
