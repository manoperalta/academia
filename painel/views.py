from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Painel
from .forms import PainelForm
from datetime import date

@login_required
def painel_list(request):
    user = request.user
    if user.is_superuser or user.is_staff:
        paineis = Painel.objects.all()
    elif hasattr(user, 'professor_profile'):
        paineis = Painel.objects.filter(responsavel=user)
    else:
        # Students might see this too? For now let's assume this view is for management.
        # But maybe students need to see the schedule.
        # The request focuses on "professor ou admin... seleciona".
        # Let's show all future panels for students if they access this, 
        # but the request implies this is a management CRUD.
        # Let's stick to the user request: "professor ou admin".
        paineis = Painel.objects.all() # Fallback or maybe filter by student enrollments later.

    return render(request, 'painel/painel_list.html', {'paineis': paineis})

@login_required
def painel_create(request):
    if request.method == 'POST':
        form = PainelForm(request.POST)
        if form.is_valid():
            painel = form.save(commit=False)
            painel.responsavel = request.user
            painel.save()
            messages.success(request, 'Agendamento no painel criado com sucesso!')
            return redirect('painel_list')
    else:
        form = PainelForm()
    
    return render(request, 'painel/painel_form.html', {'form': form, 'title': 'Novo Agendamento'})

@login_required
def painel_update(request, pk):
    painel = get_object_or_404(Painel, pk=pk)
    
    # Permission check
    if not (request.user.is_superuser or request.user.is_staff or painel.responsavel == request.user):
        messages.error(request, 'Você não tem permissão para editar este agendamento.')
        return redirect('painel_list')

    if request.method == 'POST':
        form = PainelForm(request.POST, instance=painel)
        if form.is_valid():
            form.save()
            messages.success(request, 'Agendamento atualizado com sucesso!')
            return redirect('painel_list')
    else:
        form = PainelForm(instance=painel)
    
    return render(request, 'painel/painel_form.html', {'form': form, 'title': 'Editar Agendamento'})

@login_required
def painel_delete(request, pk):
    painel = get_object_or_404(Painel, pk=pk)
    
    # Permission check
    if not (request.user.is_superuser or request.user.is_staff or painel.responsavel == request.user):
        messages.error(request, 'Você não tem permissão para excluir este agendamento.')
        return redirect('painel_list')

    if request.method == 'POST':
        painel.delete()
        messages.success(request, 'Agendamento excluído com sucesso!')
        return redirect('painel_list')
    
    return render(request, 'painel/painel_confirm_delete.html', {'painel': painel})
