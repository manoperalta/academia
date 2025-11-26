from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Painel, PainelItem
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
            
            # Save selected aulas
            aulas = form.cleaned_data.get('aulas_selecionadas')
            if aulas:
                for index, aula in enumerate(aulas):
                    PainelItem.objects.create(painel=painel, aula=aula, ordem=index)
            
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
            painel = form.save()
            
            # Update selected aulas
            PainelItem.objects.filter(painel=painel).delete()
            aulas = form.cleaned_data.get('aulas_selecionadas')
            if aulas:
                for index, aula in enumerate(aulas):
                    PainelItem.objects.create(painel=painel, aula=aula, ordem=index)
            
            messages.success(request, 'Agendamento atualizado com sucesso!')
            return redirect('painel_list')
    else:
        initial_aulas = painel.itens.values_list('aula', flat=True)
        form = PainelForm(instance=painel, initial={'aulas_selecionadas': initial_aulas})
    
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

@login_required
def presentation_setup(request):
    from aulas.models import Aulas
    aulas = Aulas.objects.all()
    return render(request, 'painel/presentation_setup.html', {'aulas': aulas})

@login_required
def presentation_view(request):
    from aulas.models import Aulas
    
    painel_id = request.GET.get('painel_id')
    aula_ids = request.GET.get('ids', '')
    playlist_data = []
    
    if painel_id:
        painel = get_object_or_404(Painel, pk=painel_id)
        # Get items ordered by 'ordem'
        items = painel.itens.select_related('aula').all()
        for item in items:
            aula = item.aula
            playlist_data.append({
                'id': aula.id,
                'title': aula.nome,
                'category': aula.get_categorias_exercicios_display(),
                'description': aula.descricao,
                'videoUrl': aula.file_de_video.url if aula.file_de_video else '',
                'hasVideo': bool(aula.file_de_video)
            })
    elif aula_ids:
        ids_list = [int(id) for id in aula_ids.split(',') if id.isdigit()]
        # Preserve order of selection
        for i in ids_list:
            try:
                aula = Aulas.objects.get(id=i)
                playlist_data.append({
                    'id': aula.id,
                    'title': aula.nome,
                    'category': aula.get_categorias_exercicios_display(),
                    'description': aula.descricao,
                    'videoUrl': aula.file_de_video.url if aula.file_de_video else '',
                    'hasVideo': bool(aula.file_de_video)
                })
            except Aulas.DoesNotExist:
                continue
    
    return render(request, 'painel/presentation_view.html', {'playlist_data': playlist_data})
