from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from agendamento.models import Agendamento
from financeiro.models import Pagamento, Despesa
from usuarios.models import Usuario
from datetime import date

@login_required
def relatorio_geral(request):
    user = request.user
    
    context = {
        'title': 'Relatório de Atividades',
        'today': date.today(),
    }

    if user.is_superuser or user.is_staff:
        # Correção do select_related para usar 'responsavel' ao invés de 'criador'
        agendamentos = Agendamento.objects.filter(aluno=user).select_related('painel', 'painel__responsavel').prefetch_related('painel__itens__aula')
    else:
        agendamentos = Agendamento.objects.filter(aluno=user).select_related('painel', 'painel__responsavel').prefetch_related('painel__itens__aula')

    historico_aulas = []
    total_aulas = agendamentos.count()
    
    categorias_stats = {}

    for agendamento in agendamentos:
        painel = agendamento.painel
        # O campo 'aulas' não existe diretamente em Painel, acessamos via itens
        itens = painel.itens.all()
        aulas = [item.aula for item in itens]
        
        for aula in aulas:
            cat = aula.get_categorias_exercicios_display()
            if cat in categorias_stats:
                categorias_stats[cat] += 1
            else:
                categorias_stats[cat] = 1

        historico_aulas.append({
            'data': painel.data, # Corrigido de data_painel para data
            'hora_inicio': painel.hora_inicio, # Corrigido nomes dos campos
            'hora_fim': painel.hora_fim,
            'responsavel': painel.responsavel.get_full_name() or painel.responsavel.username,
            'aulas': aulas,
            'status': agendamento.status
        })

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

@login_required
def relatorio_financeiro(request):
    # Todos os alunos
    usuarios = Usuario.objects.all().select_related('user')
    
    pagos = []
    devedores = []
    today = date.today()

    for usuario in usuarios:
        # Verifica se tem pagamento ativo
        pgto_ativo = Pagamento.objects.filter(usuario=usuario.user, status='pago', data_fim__gte=today).exists()
        
        # Pega o último status para exibição
        ultimo_pgto = Pagamento.objects.filter(usuario=usuario.user).order_by('-data_pagamento').first()
        status_desc = ultimo_pgto.get_status_display() if ultimo_pgto else "Sem registro"
        
        dados_usuario = {
            'nome': usuario.nome,
            'email': usuario.email_user,
            'status_financeiro': status_desc,
            'data_fim': ultimo_pgto.data_fim if ultimo_pgto else None
        }

        if pgto_ativo:
            pagos.append(dados_usuario)
        else:
            devedores.append(dados_usuario)

    context = {
        'title': 'Relatório Financeiro',
        'pagos': pagos,
        'devedores': devedores,
        'today': today,
    }
    return render(request, 'relatorios/relatorio_financeiro.html', context)

@login_required
def relatorio_usuarios(request):
    usuarios = Usuario.objects.all().order_by('nome')
    context = {
        'title': 'Relatório de Usuários',
        'usuarios': usuarios,
        'today': date.today(),
    }
    return render(request, 'relatorios/relatorio_usuarios.html', context)

@login_required
def relatorio_extrato(request):
    # Entradas (Pagamentos Pagos)
    entradas = Pagamento.objects.filter(status='pago').order_by('-data_pagamento')
    total_entradas = entradas.aggregate(Sum('valor_pago'))['valor_pago__sum'] or 0
    
    # Saídas (Despesas)
    saidas = Despesa.objects.all().order_by('-data')
    total_saidas = saidas.aggregate(Sum('valor'))['valor__sum'] or 0
    
    # Pendentes
    pendentes = Pagamento.objects.filter(status='pendente').order_by('-data_pagamento')
    total_pendentes = pendentes.aggregate(Sum('valor_pago'))['valor_pago__sum'] or 0

    saldo = total_entradas - total_saidas

    context = {
        'title': 'Relatório Extrato',
        'entradas': entradas,
        'total_entradas': total_entradas,
        'saidas': saidas,
        'total_saidas': total_saidas,
        'pendentes': pendentes,
        'total_pendentes': total_pendentes,
        'saldo': saldo,
        'today': date.today(),
    }
    return render(request, 'relatorios/relatorio_extrato.html', context)
