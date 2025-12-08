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
            
            # Contar alunos ativos
            from usuarios.models import Usuario
            total_alunos = Usuario.objects.filter(status_user='Ativo', user__is_staff=False, user__is_superuser=False).count()
            
            context.update({
                'aulas_count': aulas_count, 
                'paineis_count': paineis_count,
                'agendamentos_count': agendamentos_count,
                'total_alunos': total_alunos
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
    """Envia notificação por e-mail e/ou whatsapp para usuários com pagamento atrasado"""
    if not (request.user.is_superuser or request.user.is_staff):
        messages.error(request, 'Você não tem permissão para acessar esta funcionalidade.')
        return redirect('dashboard')
    
    if request.method == 'POST':
        from academia.models import Configuracao
        from financeiro.models import Pagamento
        from django.contrib.auth import get_user_model
        from notificacoes.models import Notificacao
        
        User = get_user_model()
        mensagem = request.POST.get('mensagem', '')
        tipo_envio = request.POST.get('tipo_envio', 'email') # 'email', 'whatsapp' ou 'ambos'
        
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
        
        enviados = 0
        
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
            
            if atrasado:
                # Enviar Email
                if tipo_envio in ['email', 'ambos'] and usuario.email:
                    try:
                        notificacao = Notificacao.objects.create(
                            assunto=f'Aviso de Pagamento - {nome_academia}',
                            mensagem=mensagem,
                            destinatarios=usuario.email,
                            tipo='email',
                            criado_por=request.user
                        )
                        if notificacao.enviar():
                            enviados += 1
                    except Exception as e:
                        print(f'Erro ao enviar e-mail para {usuario.email}: {e}')

                # Enviar WhatsApp
                if tipo_envio in ['whatsapp', 'ambos']:
                    # Tenta pegar o telefone do perfil do usuário
                    telefone = None
                    if hasattr(usuario, 'usuario_profile') and usuario.usuario_profile.telefone_user:
                        telefone = usuario.usuario_profile.telefone_user
                    
                    if telefone:
                        try:
                            notificacao = Notificacao.objects.create(
                                assunto=f'Aviso de Pagamento - {nome_academia}',
                                mensagem=mensagem,
                                destinatarios=telefone,
                                tipo='whatsapp',
                                criado_por=request.user
                            )
                            if notificacao.enviar():
                                enviados += 1
                        except Exception as e:
                            print(f'Erro ao enviar whatsapp para {telefone}: {e}')
        
        messages.success(request, f'Processo de notificação finalizado. {enviados} notificações enviadas.')
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
        from notificacoes.models import Notificacao
        
        mensagem_template = request.POST.get('mensagem', '')
        tipo_envio = request.POST.get('tipo_envio', 'email') # 'email', 'whatsapp' ou 'ambos'
        
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
        
        enviados = 0
        
        for aniversariante in aniversariantes_hoje:
            # Personalizar mensagem
            mensagem_personalizada = mensagem_template.replace('{academia}', nome_academia)
            mensagem_personalizada = mensagem_personalizada.replace('{nome}', aniversariante.nome)
            
            # Enviar Email
            if tipo_envio in ['email', 'ambos'] and aniversariante.email_user:
                try:
                    notificacao = Notificacao.objects.create(
                        assunto=f'Feliz Aniversário! - {nome_academia}',
                        mensagem=mensagem_personalizada,
                        destinatarios=aniversariante.email_user,
                        tipo='email',
                        criado_por=request.user
                    )
                    if notificacao.enviar():
                        enviados += 1
                except Exception as e:
                    print(f'Erro ao enviar e-mail para {aniversariante.email_user}: {e}')

            # Enviar WhatsApp
            if tipo_envio in ['whatsapp', 'ambos'] and aniversariante.telefone_user:
                try:
                    notificacao = Notificacao.objects.create(
                        assunto=f'Feliz Aniversário! - {nome_academia}',
                        mensagem=mensagem_personalizada,
                        destinatarios=aniversariante.telefone_user,
                        tipo='whatsapp',
                        criado_por=request.user
                    )
                    if notificacao.enviar():
                        enviados += 1
                except Exception as e:
                    print(f'Erro ao enviar whatsapp para {aniversariante.telefone_user}: {e}')
        
        messages.success(request, f'Processo de envio finalizado. {enviados} mensagens enviadas.')
        return redirect('dashboard')
    
    return redirect('dashboard')
