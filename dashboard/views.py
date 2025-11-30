from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from datetime import date, timedelta
from django.db.models import Q

@login_required
def dashboard(request):
    user = request.user
    context = {}
    
    # Check payment status for all users
    pagamento_vencido = False
    if not (user.is_superuser or user.is_staff):
        from financeiro.models import Pagamento
        ultimo_pagamento = Pagamento.objects.filter(usuario=user).order_by('-data_fim').first()
        if ultimo_pagamento:
            if ultimo_pagamento.data_fim < date.today():
                pagamento_vencido = True
        else:
            pagamento_vencido = True  # No payments recorded
        
        context['pagamento_vencido'] = pagamento_vencido
        context['ultimo_pagamento'] = ultimo_pagamento
    
    if user.is_superuser or user.is_staff:
        # Buscar configurações
        from academia.models import Configuracao
        from financeiro.models import Pagamento
        from usuarios.models import Usuario
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        
        # Obter configuração
        config = Configuracao.objects.first()
        dias_alerta = config.dias_alerta_vencimento if config else 5
        
        # Calcular estatísticas financeiras
        hoje = date.today()
        data_alerta = hoje + timedelta(days=dias_alerta)
        
        # Todos os usuários ativos (não staff/superuser)
        usuarios_ativos = User.objects.filter(
            is_active=True,
            is_staff=False,
            is_superuser=False
        )
        
        total_usuarios = usuarios_ativos.count()
        
        # Usuários com pagamento em dia (data_fim >= hoje e status pago)
        usuarios_em_dia = 0
        usuarios_alerta = 0
        usuarios_atrasados = 0
        usuarios_atrasados_lista = []
        
        for usuario in usuarios_ativos:
            ultimo_pag = Pagamento.objects.filter(
                usuario=usuario,
                status='pago'
            ).order_by('-data_fim').first()
            
            if ultimo_pag:
                if ultimo_pag.data_fim >= hoje:
                    usuarios_em_dia += 1
                elif ultimo_pag.data_fim >= hoje - timedelta(days=dias_alerta) and ultimo_pag.data_fim < hoje:
                    usuarios_alerta += 1
                else:
                    usuarios_atrasados += 1
                    usuarios_atrasados_lista.append({
                        'id': usuario.id,
                        'nome': usuario.username,
                        'email': usuario.email,
                        'dias_atraso': (hoje - ultimo_pag.data_fim).days
                    })
            else:
                # Sem pagamento = atrasado
                usuarios_atrasados += 1
                usuarios_atrasados_lista.append({
                    'id': usuario.id,
                    'nome': usuario.username,
                    'email': usuario.email,
                    'dias_atraso': 0
                })
        
        # Calcular percentuais
        if total_usuarios > 0:
            perc_em_dia = round((usuarios_em_dia / total_usuarios) * 100, 1)
            perc_alerta = round((usuarios_alerta / total_usuarios) * 100, 1)
            perc_atrasados = round((usuarios_atrasados / total_usuarios) * 100, 1)
        else:
            perc_em_dia = perc_alerta = perc_atrasados = 0
        
        # Aniversariantes do dia
        aniversariantes_hoje = Usuario.objects.filter(
            data_nasc__month=hoje.month,
            data_nasc__day=hoje.day,
            status_user='Ativo'
        )
        
        total_aniversariantes = aniversariantes_hoje.count()
        
        context.update({
            'total_usuarios': total_usuarios,
            'usuarios_em_dia': usuarios_em_dia,
            'usuarios_alerta': usuarios_alerta,
            'usuarios_atrasados': usuarios_atrasados,
            'perc_em_dia': perc_em_dia,
            'perc_alerta': perc_alerta,
            'perc_atrasados': perc_atrasados,
            'usuarios_atrasados_lista': usuarios_atrasados_lista,
            'total_aniversariantes': total_aniversariantes,
            'aniversariantes_hoje': aniversariantes_hoje,
            'config': config,
            'dias_alerta': dias_alerta,
        })
        
        return render(request, 'dashboard/dashboard.html', context)
    elif user.is_professor:
        # Verificar status do professor
        if hasattr(user, 'professor_profile') and user.professor_profile.status_prof == 'Ativo':
            from aulas.models import Aulas
            from painel.models import Painel
            from agendamento.models import Agendamento
            
            aulas_count = Aulas.objects.filter(professor=user).count()
            paineis_count = Painel.objects.filter(responsavel=user).count()
            
            # Contar agendamentos nos painéis criados pelo professor
            agendamentos_count = Agendamento.objects.filter(painel__responsavel=user).count()
            
            context.update({
                'aulas_count': aulas_count, 
                'paineis_count': paineis_count,
                'agendamentos_count': agendamentos_count
            })
            return render(request, 'dashboard/dashboard_prof.html', context)
        else:
            return render(request, 'dashboard/aguardando_aprovacao.html', context)
    elif user.is_student:
        return render(request, 'dashboard/dashboard_user.html', context)
    else:
        return render(request, 'dashboard/dashboard_user.html', context) # Default fallback


@login_required
def enviar_notificacao_atraso(request):
    """Envia notificação por e-mail para usuários com pagamento atrasado"""
    if not (request.user.is_superuser or request.user.is_staff):
        messages.error(request, 'Você não tem permissão para acessar esta funcionalidade.')
        return redirect('dashboard')
    
    if request.method == 'POST':
        from academia.models import Configuracao
        from financeiro.models import Pagamento
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        mensagem = request.POST.get('mensagem', '')
        
        # Obter configuração
        config = Configuracao.objects.first()
        nome_academia = config.titulo if config else 'Academia'
        
        # Calcular usuários atrasados
        hoje = date.today()
        usuarios_ativos = User.objects.filter(
            is_active=True,
            is_staff=False,
            is_superuser=False
        )
        
        emails_enviados = 0
        
        for usuario in usuarios_ativos:
            ultimo_pag = Pagamento.objects.filter(
                usuario=usuario,
                status='pago'
            ).order_by('-data_fim').first()
            
            # Verificar se está atrasado
            atrasado = False
            if ultimo_pag:
                if ultimo_pag.data_fim < hoje:
                    atrasado = True
            else:
                atrasado = True
            
            if atrasado and usuario.email:
                try:
                    send_mail(
                        subject=f'Aviso de Pagamento - {nome_academia}',
                        message=mensagem,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[usuario.email],
                        fail_silently=False,
                    )
                    emails_enviados += 1
                except Exception as e:
                    print(f'Erro ao enviar e-mail para {usuario.email}: {e}')
        
        messages.success(request, f'Notificação enviada com sucesso para {emails_enviados} usuário(s)!')
        return redirect('dashboard')
    
    return redirect('dashboard')


@login_required
def enviar_mensagem_aniversario(request):
    """Envia mensagem de aniversário para aniversariantes do dia"""
    if not (request.user.is_superuser or request.user.is_staff):
        messages.error(request, 'Você não tem permissão para acessar esta funcionalidade.')
        return redirect('dashboard')
    
    if request.method == 'POST':
        from academia.models import Configuracao
        from usuarios.models import Usuario
        
        mensagem_template = request.POST.get('mensagem', '')
        
        # Obter configuração
        config = Configuracao.objects.first()
        nome_academia = config.titulo if config else 'Academia'
        
        # Aniversariantes do dia
        hoje = date.today()
        aniversariantes_hoje = Usuario.objects.filter(
            data_nasc__month=hoje.month,
            data_nasc__day=hoje.day,
            status_user='Ativo'
        )
        
        emails_enviados = 0
        
        for aniversariante in aniversariantes_hoje:
            if aniversariante.email_user:
                # Personalizar mensagem
                mensagem_personalizada = mensagem_template.replace('{academia}', nome_academia)
                mensagem_personalizada = mensagem_personalizada.replace('{nome}', aniversariante.nome)
                
                try:
                    send_mail(
                        subject=f'Feliz Aniversário! - {nome_academia}',
                        message=mensagem_personalizada,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[aniversariante.email_user],
                        fail_silently=False,
                    )
                    emails_enviados += 1
                except Exception as e:
                    print(f'Erro ao enviar e-mail para {aniversariante.email_user}: {e}')
        
        messages.success(request, f'Mensagem de aniversário enviada com sucesso para {emails_enviados} pessoa(s)!')
        return redirect('dashboard')
    
    return redirect('dashboard')
