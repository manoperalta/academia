from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from .models import Agendamento
from painel.models import Painel

# --- Views do Aluno ---

@login_required
def agenda_list(request):
    # Se for professor ou staff, mostra a agenda dele com os alunos inscritos
    if request.user.is_professor or request.user.is_staff:
        # Mostrar painéis futuros e passados recentes (opcional, aqui mostrando futuros)
        # ou todos ordenados por data decrescente para ver histórico?
        # O pedido diz "coletar dados dos alunos que selecionaram determinado horario"
        # Vamos mostrar do mais recente para o futuro
        paineis = Painel.objects.filter(responsavel=request.user).order_by('-data', 'hora_inicio')
        return render(request, 'agendamento/professor_agenda.html', {'paineis': paineis})

    if not request.user.is_student:
        return redirect('dashboard')
    
    # Mostrar apenas painéis futuros
    hoje = timezone.now().date()
    paineis = Painel.objects.filter(data__gte=hoje).order_by('data', 'hora_inicio')
    
    # Adicionar informação se o aluno já está inscrito
    for painel in paineis:
        painel.inscrito = Agendamento.objects.filter(painel=painel, aluno=request.user, status='Agendado').exists()
        agendamentos_count = painel.agendamentos.filter(status='Agendado').count()
        painel.total_agendados = agendamentos_count
        
        # Se tem limite, calcular vagas restantes
        if painel.numero_de_user:
            painel.vagas_restantes = painel.numero_de_user - agendamentos_count
            painel.tem_limite = True
        else:
            painel.vagas_restantes = None  # Sem limite
            painel.tem_limite = False

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
        
    # Verificar vagas apenas se houver limite
    if painel.numero_de_user:
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
        
    agendamentos = Agendamento.objects.filter(aluno=request.user).order_by('-painel__data')
    return render(request, 'agendamento/meus_agendamentos.html', {'agendamentos': agendamentos})

@login_required
def cancelar_agendamento(request, agendamento_id):
    agendamento = get_object_or_404(Agendamento, pk=agendamento_id, aluno=request.user)
    
    if agendamento.status == 'Agendado':
        agendamento.status = 'Cancelado'
        agendamento.save()
        messages.success(request, 'Agendamento cancelado com sucesso.')
    
    return redirect('meus_agendamentos')
