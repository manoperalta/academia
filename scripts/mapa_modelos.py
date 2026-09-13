"""Imprime apps instalados e os campos dos modelos que interessam ao painel do professor."""

from __future__ import annotations

from django.apps import apps

INTERESSA = {
    "professores",
    "aulas",
    "agendamento",
    "turmas",
    "usuarios",
    "financeiro",
    "treinos",
    "avaliacoes",
    "avaliacao",
    "alunos",
    "core",
    "notificacoes",
    "relatorios",
}

print("=== APPS INSTALADOS ===")
for config in apps.get_app_configs():
    print(config.label, "|", config.name)

print()
print("=== MODELOS DOS APPS DE INTERESSE ===")
for config in apps.get_app_configs():
    if config.label not in INTERESSA:
        continue
    for modelo in config.get_models():
        campos = []
        for campo in modelo._meta.get_fields():
            if getattr(campo, "auto_created", False) and not getattr(campo, "concrete", False):
                continue
            nome = campo.name
            if hasattr(campo, "get_internal_type"):
                campos.append(f"{nome}:{campo.get_internal_type()}")
        print(f"--- {config.label}.{modelo.__name__}: {', '.join(campos[:26])}")
