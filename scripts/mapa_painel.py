"""Campos dos modelos de grade/turma (app painel) e do agendamento."""
from __future__ import annotations

from django.apps import apps

for label in ("painel", "agendamento", "aulas"):
    config = apps.get_app_config(label)
    for modelo in config.get_models():
        campos = []
        for campo in modelo._meta.get_fields():
            if getattr(campo, "auto_created", False) and not getattr(campo, "concrete", False):
                continue
            tipo = campo.get_internal_type() if hasattr(campo, "get_internal_type") else "?"
            alvo = ""
            if tipo == "ForeignKey":
                alvo = "->" + getattr(campo, "related_model", None).__name__ if getattr(campo, "related_model", None) else ""
            campos.append(f"{campo.name}:{tipo}{alvo}")
        print(f"--- {label}.{modelo.__name__}: {', '.join(campos)}")
