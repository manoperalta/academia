from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Aulas
from .forms import AulasForm, ImagemAulaFormSet

@login_required
def aulas_list(request):
    if not request.user.is_professor:
        return redirect('dashboard')
    
    aulas = Aulas.objects.filter(professor=request.user)
    return render(request, 'aulas/aulas_list.html', {'aulas': aulas})

@login_required
def aulas_create(request):
    if not request.user.is_professor:
        return redirect('dashboard')

    if request.method == 'POST':
        form = AulasForm(request.POST, request.FILES)
        formset = ImagemAulaFormSet(request.POST, request.FILES)
        
        if form.is_valid() and formset.is_valid():
            aula = form.save(commit=False)
            aula.professor = request.user
            aula.save()
            
            formset.instance = aula
            formset.save()
            
            messages.success(request, 'Aula criada com sucesso!')
            return redirect('aulas_list')
    else:
        form = AulasForm()
        formset = ImagemAulaFormSet()
    
    return render(request, 'aulas/aulas_form.html', {
        'form': form,
        'formset': formset,
        'title': 'Nova Aula'
    })

@login_required
def aulas_update(request, pk):
    aula = get_object_or_404(Aulas, pk=pk, professor=request.user)
    
    if request.method == 'POST':
        form = AulasForm(request.POST, request.FILES, instance=aula)
        formset = ImagemAulaFormSet(request.POST, request.FILES, instance=aula)
        
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, 'Aula atualizada com sucesso!')
            return redirect('aulas_list')
    else:
        form = AulasForm(instance=aula)
        formset = ImagemAulaFormSet(instance=aula)
    
    return render(request, 'aulas/aulas_form.html', {
        'form': form,
        'formset': formset,
        'title': 'Editar Aula'
    })

@login_required
def aulas_delete(request, pk):
    aula = get_object_or_404(Aulas, pk=pk, professor=request.user)
    
    if request.method == 'POST':
        aula.delete()
        messages.success(request, 'Aula excluída com sucesso!')
        return redirect('aulas_list')
        
    return render(request, 'aulas/aulas_confirm_delete.html', {'aula': aula})
