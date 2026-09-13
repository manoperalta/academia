"""Imprime as escolhas (choices) dos campos que o povoamento usa."""

from __future__ import annotations

from django.apps import apps

ALVOS = [
    ("financeiro", "Pagamento", "status"),
    ("agendamento", "Agendamento", "status"),
    ("usuarios", "Usuario", "status_user"),
    ("professores", "Professor", "status_prof"),
    ("cobranca", "CobrancaRecorrente", "situacao"),
    ("relacionamento", "Lead", "situacao"),
    ("relacionamento", "Lead", "origem"),
    ("core", "Unidade", "tipo"),
    ("core", "Unidade", "status"),
    ("treinos", "Treino", "situacao"),
    ("plataforma", "Assinatura", "ciclo"),
    ("nps", "Pesquisa", "situacao"),
]

for app, modelo, campo in ALVOS:
    try:
        classe = apps.get_model(app, modelo)
        campo_meta = classe._meta.get_field(campo)
        escolhas = [valor for valor, _ in (campo_meta.choices or [])]
        print(f"{app}.{modelo}.{campo}: {escolhas or 'sem choices'}")
    except Exception as erro:
        print(f"{app}.{modelo}.{campo}: ERRO {type(erro).__name__}: {erro}")

print("--- modelos do app nps ---")
print([modelo.__name__ for modelo in apps.get_app_config("nps").get_models()])
print("--- modelos do app gamificacao ---")
print([modelo.__name__ for modelo in apps.get_app_config("gamificacao").get_models()])
