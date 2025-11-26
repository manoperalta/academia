from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from datetime import date

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
        return render(request, 'dashboard/dashboard.html', context)
    elif user.is_professor:
        # Verificar status do professor
        if hasattr(user, 'professor_profile') and user.professor_profile.status_prof == 'Ativo':
            from aulas.models import Aulas
            from painel.models import Painel
            aulas_count = Aulas.objects.filter(professor=user).count()
            paineis_count = Painel.objects.filter(responsavel=user).count()
            context.update({'aulas_count': aulas_count, 'paineis_count': paineis_count})
            return render(request, 'dashboard/dashboard_prof.html', context)
        else:
            return render(request, 'dashboard/aguardando_aprovacao.html', context)
    elif user.is_student:
        return render(request, 'dashboard/dashboard_user.html', context)
    else:
        return render(request, 'dashboard/dashboard_user.html', context) # Default fallback
