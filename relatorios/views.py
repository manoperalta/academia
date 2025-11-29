from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from agendamento.models import Agendamento
from financeiro.models import Pagamento
from datetime import date

@login_required
def relatorio_geral(request):
    user = request.user
    
    # Contexto base
    context = {
        'title': 'Relatório de Atividades',
        'today': date.today(),
    }

    # Filtra agendamentos
    if user.is_superuser or user.is_staff:
        # Se for admin, pode ver tudo (por enquanto vamos focar no usuário logado ou permitir busca futura)
        # Para simplificar e atender o requisito de "relacionar as aulas do usuario", vamos mostrar o do usuário logado
        # ou se tiver um parametro 'user_id' na URL (futuro).
        # Vamos mostrar o do próprio admin se ele for aluno também, ou listar todos se for dashboard geral.
        # O pedido diz "relacionar as aulas do usuarios" (plural?).
        # Vamos fazer um relatório pessoal primeiro.
        agendamentos = Agendamento.objects.filter(aluno=user).select_related('painel', 'painel__criador').prefetch_related('painel__aulas')
    else:
        agendamentos = Agendamento.objects.filter(aluno=user).select_related('painel', 'painel__criador').prefetch_related('painel__aulas')

    # Processa dados para o relatório
    historico_aulas = []
    total_aulas = agendamentos.count()
    
    # Agrupa por modalidade/categoria se possível (assumindo que Aula tem categoria)
    categorias_stats = {}

    for agendamento in agendamentos:
        painel = agendamento.painel
        aulas = painel.aulas.all()
        
        # Coleta categorias para estatísticas
        for aula in aulas:
            cat = aula.get_categorias_exercicios_display() # Assumindo que tem esse método/campo
            if cat in categorias_stats:
                categorias_stats[cat] += 1
            else:
                categorias_stats[cat] = 1

        historico_aulas.append({
            'data': painel.data_painel,
            'hora_inicio': painel.horario_inicial_painel,
            'hora_fim': painel.horario_final_painel,
            'professor': painel.criador.get_full_name() or painel.criador.username,
            'aulas': aulas,
            'status': agendamento.status
        })

    # Dados Financeiros
    pagamento_atual = Pagamento.objects.filter(usuario=user, status='pago', data_fim__gte=date.today()).first()
    ultimo_pagamento = Pagamento.objects.filter(usuario=user).order_by('-data_pagamento').first()

    context.update({
        'historico_aulas': historico_aulas,
        'total_aulas': total_aulas,
        'categorias_stats': categorias_stats,
        'pagamento_atual': pagamento_atual,
        'ultimo_pagamento': ultimo_pagamento,
    })

    return render(request, 'relatorios/relatorio_geral.html', context)
