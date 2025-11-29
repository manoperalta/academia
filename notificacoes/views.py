from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from .forms import NotificacaoForm
from .models import Notificacao

def is_admin(user):
    return user.is_superuser or user.is_staff

@login_required
@user_passes_test(is_admin)
def criar_notificacao(request):
    if request.method == 'POST':
        form = NotificacaoForm(request.POST)
        if form.is_valid():
            notificacao = form.save(commit=False)
            notificacao.criado_por = request.user
            notificacao.save()
            
            # Tenta enviar imediatamente
            if notificacao.enviar():
                messages.success(request, 'Notificação criada e enviada com sucesso!')
            else:
                messages.warning(request, 'Notificação criada, mas houve erro no envio. Verifique o log no admin.')
            
            return redirect('dashboard')
    else:
        form = NotificacaoForm()
    
    return render(request, 'notificacoes/criar_notificacao_modal.html', {'form': form})
