from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Professor
from .forms import ProfessorForm, ProfessorProfileForm

@login_required
def professor_list(request):
    professores = Professor.objects.all()
    return render(request, 'professores/professor_list.html', {'professores': professores})

@login_required
def professor_create(request):
    if request.method == 'POST':
        form = ProfessorForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Professor criado com sucesso!')
            return redirect('professor_list')
    else:
        form = ProfessorForm()
    return render(request, 'professores/professor_form.html', {'form': form, 'title': 'Novo Professor'})

@login_required
def professor_update(request, pk):
    professor = get_object_or_404(Professor, pk=pk)
    if request.method == 'POST':
        form = ProfessorForm(request.POST, instance=professor)
        if form.is_valid():
            form.save()
            messages.success(request, 'Professor atualizado com sucesso!')
            return redirect('professor_list')
    else:
        form = ProfessorForm(instance=professor)
    return render(request, 'professores/professor_form.html', {'form': form, 'title': 'Editar Professor'})

@login_required
def professor_delete(request, pk):
    professor = get_object_or_404(Professor, pk=pk)
    if request.method == 'POST':
        professor.delete()
        messages.success(request, 'Professor excluído com sucesso!')
        return redirect('professor_list')
    return render(request, 'professores/professor_confirm_delete.html', {'professor': professor})

@login_required
def complete_profile_professor(request):
    # Tenta obter o perfil do professor logado
    try:
        professor = request.user.professor_profile
    except Professor.DoesNotExist:
        # Se não existir, cria um
        professor = Professor.objects.create(user=request.user, nome=request.user.username)

    if request.method == 'POST':
        form = ProfessorProfileForm(request.POST, request.FILES, instance=professor)
        if form.is_valid():
            form.save()
            messages.success(request, 'Perfil completado com sucesso!')
            return redirect('dashboard')
    else:
        form = ProfessorProfileForm(instance=professor)
    
    return render(request, 'professores/complete_profile.html', {'form': form})
