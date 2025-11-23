from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from .models import Painel, Agendamento
from .forms import PainelForm

# --- Views do Professor ---

@login_required
def painel_list(request):
    if not request.user.is_professor:
        return redirect('dashboard')
    
    paineis = Painel.objects.filter(criador=request.user).order_by('-data_painel', 'horario_inicial_painel')
    return render(request, 'agendamento/painel_list.html', {'paineis': paineis})

@login_required
def painel_create(request):
    if not request.user.is_professor:
        return redirect('dashboard')

    if request.method == 'POST':
        form = PainelForm(request.user, request.POST)
        if form.is_valid():
            painel = form.save(commit=False)
            painel.criador = request.user
            painel.save()
            form.save_m2m() # Salvar relação ManyToMany
            messages.success(request, 'Painel de agendamento criado com sucesso!')
            return redirect('painel_list')
    else:
        form = PainelForm(request.user)
    
    return render(request, 'agendamento/painel_form.html', {'form': form, 'title': 'Novo Painel'})

@login_required
def painel_update(request, pk):
    painel = get_object_or_404(Painel, pk=pk, criador=request.user)
    
    if request.method == 'POST':
        form = PainelForm(request.user, request.POST, instance=painel)
        if form.is_valid():
            form.save()
            messages.success(request, 'Painel atualizado com sucesso!')
            return redirect('painel_list')
    else:
        form = PainelForm(request.user, instance=painel)
    
    return render(request, 'agendamento/painel_form.html', {'form': form, 'title': 'Editar Painel'})

# --- Views do Aluno ---

@login_required
def agenda_list(request):
    if not request.user.is_student:
        return redirect('dashboard')
    
    # Mostrar apenas painéis futuros
    hoje = timezone.now().date()
    paineis = Painel.objects.filter(data_painel__gte=hoje).order_by('data_painel', 'horario_inicial_painel')
    
    # Adicionar informação se o aluno já está inscrito
    for painel in paineis:
        painel.inscrito = Agendamento.objects.filter(painel=painel, aluno=request.user, status='Agendado').exists()
        painel.vagas_restantes = painel.numero_de_user - painel.agendamentos.filter(status='Agendado').count()

    return render(request, 'agendamento/agenda_list.html', {'paineis': paineis})

@login_required
def realizar_agendamento(request, painel_id):
    if not request.user.is_student:
        return redirect('dashboard')
        
    painel = get_object_or_404(Painel, pk=painel_id)
    
    # Verificar se já existe agendamento
    if Agendamento.objects.filter(painel=painel, aluno=request.user, status='Agendado').exists():
        messages.warning(request, 'Você já está agendado para este painel.')
        return redirect('agenda_list')
        
    # Verificar vagas
    agendamentos_ativos = painel.agendamentos.filter(status='Agendado').count()
    if agendamentos_ativos >= painel.numero_de_user:
        messages.error(request, 'Este painel não tem mais vagas disponíveis.')
        return redirect('agenda_list')
        
    Agendamento.objects.create(painel=painel, aluno=request.user, status='Agendado')
    messages.success(request, 'Agendamento realizado com sucesso!')
    return redirect('meus_agendamentos')

@login_required
def meus_agendamentos(request):
    if not request.user.is_student:
        return redirect('dashboard')
        
    agendamentos = Agendamento.objects.filter(aluno=request.user).order_by('-painel__data_painel')
    return render(request, 'agendamento/meus_agendamentos.html', {'agendamentos': agendamentos})

@login_required
def cancelar_agendamento(request, agendamento_id):
    agendamento = get_object_or_404(Agendamento, pk=agendamento_id, aluno=request.user)
    
    if agendamento.status == 'Agendado':
        agendamento.status = 'Cancelado'
        agendamento.save()
        messages.success(request, 'Agendamento cancelado com sucesso.')
    
    return redirect('meus_agendamentos')
