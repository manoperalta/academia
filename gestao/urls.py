"""Rotas do painel do tenant (/gestao/)."""

from django.urls import path

from gestao import views

app_name = "gestao"

urlpatterns = [
    path("", views.VisaoGeralView.as_view(), name="visao_geral"),
    path("configuracao/", views.OnboardingView.as_view(), name="onboarding"),
    path("plano/", views.MeuPlanoView.as_view(), name="plano"),
    path("plano/<int:pk>/mudar/", views.MudarPacoteView.as_view(), name="plano_mudar"),
    path("importar/", views.ImportarView.as_view(), name="importar"),
    path("importar/modelo.csv", views.ImportarModeloView.as_view(), name="importar_modelo"),
    path("seguranca/", views.SegurancaView.as_view(), name="seguranca"),
    path("privacidade/", views.PrivacidadeView.as_view(), name="privacidade"),
    path(
        "privacidade/solicitacoes/",
        views.SolicitacaoTitularView.as_view(),
        name="privacidade_solicitar",
    ),
    path(
        "privacidade/solicitacoes/<int:pk>/concluir/",
        views.ConcluirSolicitacaoView.as_view(),
        name="privacidade_concluir",
    ),
    path(
        "privacidade/aluno/<int:pk>/exportar/",
        views.ExportarTitularView.as_view(),
        name="privacidade_exportar",
    ),
    path(
        "privacidade/aluno/<int:pk>/anonimizar/",
        views.AnonimizarTitularView.as_view(),
        name="privacidade_anonimizar",
    ),
    path("dominio/", views.DominioView.as_view(), name="dominio"),
    path("dominio/verificar/", views.VerificarDominioView.as_view(), name="dominio_verificar"),
    path("unidade/", views.SelecionarUnidadeView.as_view(), name="selecionar_unidade"),
    path("auditoria/", views.AuditoriaView.as_view(), name="auditoria"),
    path("equipe/", views.EquipeView.as_view(), name="equipe"),
    path("equipe/convidar/", views.ConviteNovo.as_view(), name="convite_novo"),
    path(
        "equipe/convite/<int:pk>/cancelar/",
        views.ConviteCancelar.as_view(),
        name="convite_cancelar",
    ),
    path(
        "equipe/vinculo/<int:pk>/alternar/",
        views.VinculoAlternar.as_view(),
        name="vinculo_alternar",
    ),
    path("convite/<str:token>/", views.ConviteAceitarView.as_view(), name="convite_aceitar"),
    # alunos
    path("alunos/", views.AlunosView.as_view(), name="alunos"),
    path("alunos/novo/", views.AlunoNovo.as_view(), name="aluno_novo"),
    path("alunos/<int:pk>/", views.AlunoDetalheView.as_view(), name="aluno_detalhe"),
    path("alunos/<int:pk>/editar/", views.AlunoEditar.as_view(), name="aluno_editar"),
    path("alunos/<int:pk>/arquivar/", views.AlunoArquivar.as_view(), name="aluno_arquivar"),
    # professores
    path("professores/", views.ProfessoresView.as_view(), name="professores"),
    path("professores/novo/", views.ProfessorNovo.as_view(), name="professor_novo"),
    path("professores/<int:pk>/editar/", views.ProfessorEditar.as_view(), name="professor_editar"),
    path(
        "professores/<int:pk>/arquivar/",
        views.ProfessorArquivar.as_view(),
        name="professor_arquivar",
    ),
    # aulas
    path("aulas/", views.AulasView.as_view(), name="aulas"),
    path("aulas/nova/", views.AulaNova.as_view(), name="aula_nova"),
    path("aulas/<int:pk>/editar/", views.AulaEditar.as_view(), name="aula_editar"),
    path("aulas/<int:pk>/arquivar/", views.AulaArquivar.as_view(), name="aula_arquivar"),
    # agenda
    path("agenda/", views.AgendaView.as_view(), name="agenda"),
    path("agenda/nova/", views.PainelNovo.as_view(), name="painel_novo"),
    path("agenda/<int:pk>/editar/", views.PainelEditar.as_view(), name="painel_editar"),
    path(
        "agenda/agendamento/<int:pk>/checkin/",
        views.AgendamentoConcluir.as_view(),
        name="agendamento_checkin",
    ),
    # financeiro
    path("financeiro/", views.FinanceiroView.as_view(), name="financeiro"),
    path("financeiro/planos/", views.PlanosView.as_view(), name="planos"),
    path("financeiro/planos/novo/", views.PlanoNovo.as_view(), name="plano_novo"),
    path("financeiro/planos/<int:pk>/editar/", views.PlanoEditar.as_view(), name="plano_editar"),
    path(
        "financeiro/planos/<int:pk>/arquivar/", views.PlanoArquivar.as_view(), name="plano_arquivar"
    ),
    path("financeiro/pagamentos/", views.PagamentosView.as_view(), name="pagamentos"),
    path("financeiro/pagamentos/novo/", views.PagamentoNovo.as_view(), name="pagamento_novo"),
    path(
        "financeiro/pagamentos/<int:pk>/editar/",
        views.PagamentoEditar.as_view(),
        name="pagamento_editar",
    ),
    path(
        "financeiro/pagamentos/<int:pk>/baixar/",
        views.PagamentoBaixar.as_view(),
        name="pagamento_baixar",
    ),
    path("financeiro/despesas/", views.DespesasView.as_view(), name="despesas"),
    path("financeiro/despesas/nova/", views.DespesaNova.as_view(), name="despesa_nova"),
    path(
        "financeiro/despesas/<int:pk>/editar/", views.DespesaEditar.as_view(), name="despesa_editar"
    ),
    # relatorios
    path("relatorios/", views.RelatoriosView.as_view(), name="relatorios"),
    path("relatorios/alunos.csv", views.RelatorioAlunosCsv.as_view(), name="relatorio_alunos_csv"),
    path(
        "relatorios/pagamentos.csv",
        views.RelatorioPagamentosCsv.as_view(),
        name="relatorio_pagamentos_csv",
    ),
    # comunicacao e identidade
    path("comunicacao/", views.ComunicacaoView.as_view(), name="comunicacao"),
    path("comunicacao/teste/", views.ComunicacaoTesteView.as_view(), name="comunicacao_teste"),
    path("identidade/", views.IdentidadeView.as_view(), name="identidade"),
]
