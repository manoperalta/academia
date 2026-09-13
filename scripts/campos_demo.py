"""Campos dos modelos que o povoamento da demonstracao precisa."""

from __future__ import annotations

from django.apps import apps


def campos(rotulo: str) -> None:
    app, modelo = rotulo.split(".")
    classe = apps.get_model(app, modelo)
    nomes = [campo.name for campo in classe._meta.get_fields() if hasattr(campo, "attname")]
    print(f"{rotulo}: {', '.join(nomes)}")


for rotulo in [
    "core.Rede",
    "core.Unidade",
    "core.VinculoUsuario",
    "core.RegistroAuditoria",
    "usuarios.Usuario",
    "usuarios.FichaSaude",
    "professores.Professor",
    "financeiro.Plano",
    "financeiro.Pagamento",
    "agendamento.Agendamento",
    "painel.Painel",
    "painel.PainelItem",
    "aulas.Aulas",
    "notificacoes.Notificacao",
    "treinos.Treino",
    "treinos.ExercicioDoTreino",
    "treinos.AvaliacaoFisica",
    "cobranca.CobrancaRecorrente",
    "relacionamento.Lead",
    "nps.RespostaDeNps",
    "plataforma.Pacote",
    "plataforma.Assinatura",
    "api.RegistroAuditoria",
]:
    try:
        campos(rotulo)
    except Exception as erro:
        print(f"{rotulo}: ERRO {type(erro).__name__}: {erro}")
