"""Diagnostico dos estaticos da demonstracao."""

from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.urls import get_resolver

print("ROOT_URLCONF....:", settings.ROOT_URLCONF)
print("FORCE_SCRIPT....:", settings.FORCE_SCRIPT_NAME)
print("STATIC_URL......:", settings.STATIC_URL)
print("STATIC_ROOT.....:", settings.STATIC_ROOT)
print("existe tokens...:", (Path(settings.STATIC_ROOT) / "design" / "tokens.css").exists())
print("existe admin css:", (Path(settings.STATIC_ROOT) / "admin" / "css" / "base.css").exists())
padroes = [str(p.pattern) for p in get_resolver().url_patterns]
print("primeiros padroes:", padroes[:6])
print("padroes de arquivo:", [p for p in padroes if "static" in p or "media" in p][:6])
