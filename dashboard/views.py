from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required

@login_required
def dashboard(request):
    user = request.user
    if user.is_superuser or user.is_staff:
        return render(request, 'dashboard/dashboard.html')
    elif user.is_professor:
        # Verificar status do professor
        if hasattr(user, 'professor_profile') and user.professor_profile.status_prof == 'Ativo':
            return render(request, 'dashboard/dashboard_prof.html')
        else:
            return render(request, 'dashboard/aguardando_aprovacao.html')
    elif user.is_student:
        return render(request, 'dashboard/dashboard_user.html')
    else:
        return render(request, 'dashboard/dashboard_user.html') # Default fallback
