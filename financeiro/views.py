from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Pagamento, Plano, GatewayConfig
from .forms import PagamentoForm, PlanoForm
from datetime import date
from .pagbank_service import PagBankService
import logging

logger = logging.getLogger(__name__)

@login_required
def pagamento_list(request):
    if getattr(request.user, 'is_professor', False):
        messages.error(request, 'Professores não possuem acesso à área financeira.')
        return redirect('dashboard')

    if request.user.is_superuser or request.user.is_staff:
        pagamentos = Pagamento.objects.all().select_related('usuario', 'plano')
    else:
        pagamentos = Pagamento.objects.filter(usuario=request.user).select_related('plano')
    
    return render(request, 'financeiro/pagamento_list.html', {'pagamentos': pagamentos})

@login_required
def pagamento_create(request):
    if not (request.user.is_superuser or request.user.is_staff):
        messages.error(request, 'Você não tem permissão para registrar pagamentos.')
        return redirect('pagamento_list')
    
    if request.method == 'POST':
        form = PagamentoForm(request.POST)
        if form.is_valid():
            pagamento = form.save(commit=False)
            # Define status inicial como pendente se não informado
            if not pagamento.status:
                pagamento.status = 'pendente'
            pagamento.save()
            messages.success(request, 'Pagamento registrado com sucesso!')
            return redirect('pagamento_list')
    else:
        form = PagamentoForm()
    
    return render(request, 'financeiro/pagamento_form.html', {'form': form, 'title': 'Registrar Pagamento'})

@login_required
def pagamento_delete(request, pk):
    pagamento = get_object_or_404(Pagamento, pk=pk)
    
    if not (request.user.is_superuser or request.user.is_staff):
        messages.error(request, 'Você não tem permissão para excluir pagamentos.')
        return redirect('pagamento_list')
    
    if request.method == 'POST':
        pagamento.delete()
        messages.success(request, 'Pagamento excluído com sucesso!')
        return redirect('pagamento_list')
    
    return render(request, 'financeiro/pagamento_confirm_delete.html', {'pagamento': pagamento})

@login_required
def plano_list(request):
    planos = Plano.objects.all()
    return render(request, 'financeiro/plano_list.html', {'planos': planos})

@login_required
def plano_create(request):
    if not (request.user.is_superuser or request.user.is_staff):
        messages.error(request, 'Acesso negado.')
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = PlanoForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, 'Plano criado com sucesso!')
            return redirect('plano_list')
    else:
        form = PlanoForm()
    
    return render(request, 'financeiro/plano_form.html', {'form': form, 'title': 'Novo Plano'})

@login_required
def plano_update(request, pk):
    if not (request.user.is_superuser or request.user.is_staff):
        messages.error(request, 'Acesso negado.')
        return redirect('dashboard')
    
    plano = get_object_or_404(Plano, pk=pk)
    if request.method == 'POST':
        form = PlanoForm(request.POST, request.FILES, instance=plano)
        if form.is_valid():
            form.save()
            messages.success(request, 'Plano atualizado com sucesso!')
            return redirect('plano_list')
    else:
        form = PlanoForm(instance=plano)
    
    return render(request, 'financeiro/plano_form.html', {'form': form, 'title': 'Editar Plano'})

@login_required
def plano_delete(request, pk):
    if not (request.user.is_superuser or request.user.is_staff):
        messages.error(request, 'Acesso negado.')
        return redirect('dashboard')
    
    plano = get_object_or_404(Plano, pk=pk)
    if request.method == 'POST':
        plano.delete()
        messages.success(request, 'Plano excluído com sucesso!')
        return redirect('plano_list')
    
    return render(request, 'financeiro/plano_confirm_delete.html', {'plano': plano})

@login_required
def realizar_checkout(request, pk):
    pagamento = get_object_or_404(Pagamento, pk=pk)
    
    # Verifica se o usuário é o dono do pagamento ou admin
    if pagamento.usuario != request.user and not (request.user.is_superuser or request.user.is_staff):
        messages.error(request, "Você não tem permissão para acessar este pagamento.")
        return redirect('pagamento_list')

    # Se já estiver pago, redireciona
    if pagamento.status == 'pago':
        messages.info(request, "Este pagamento já foi concluído.")
        return redirect('pagamento_list')

    # Se já tem QR Code gerado, vai para detalhes
    if pagamento.qr_code_text:
        return redirect('pagamento_detalhe', pk=pagamento.pk)

    try:
        service = PagBankService()
        resultado = service.criar_pedido(pagamento, request.user)
        
        # Atualiza o pagamento com os dados retornados
        pagamento.transaction_id = resultado.get('id')
        
        # Procura por links de pagamento ou QR Codes na resposta
        qr_codes = resultado.get('qr_codes', [])
        if qr_codes:
            pagamento.qr_code_text = qr_codes[0].get('text')
            links = qr_codes[0].get('links', [])
            for link in links:
                if link.get('rel') == 'QRCODE.PNG':
                    pagamento.qr_code_base64 = link.get('href')
        
        links_pedido = resultado.get('links', [])
        for link in links_pedido:
            if link.get('rel') == 'PAY':
                pagamento.link_pagamento = link.get('href')
        
        pagamento.save()
        messages.success(request, "Pedido de pagamento gerado com sucesso!")
        return redirect('pagamento_detalhe', pk=pagamento.pk)
        
    except Exception as e:
        logger.error(f"Erro no checkout: {e}")
        messages.error(request, f"Erro ao gerar pagamento: {str(e)}")
        return redirect('pagamento_list')

@login_required
def pagamento_detalhe(request, pk):
    pagamento = get_object_or_404(Pagamento, pk=pk)
    
    if pagamento.usuario != request.user and not (request.user.is_superuser or request.user.is_staff):
        messages.error(request, "Você não tem permissão para acessar este pagamento.")
        return redirect('pagamento_list')
        
    return render(request, 'financeiro/pagamento_detalhe.html', {'pagamento': pagamento})

@login_required
def comprar_plano(request, pk):
    plano = get_object_or_404(Plano, pk=pk)
    
    # Verifica se já existe um pagamento pendente para este plano e usuário
    pagamento_pendente = Pagamento.objects.filter(
        usuario=request.user, 
        plano=plano, 
        status='pendente'
    ).first()
    
    if pagamento_pendente:
        return redirect('realizar_checkout', pk=pagamento_pendente.pk)
    
    # Cria novo pagamento
    pagamento = Pagamento.objects.create(
        usuario=request.user,
        plano=plano,
        valor_pago=plano.valor,
        data_inicio=date.today(),
        status='pendente'
    )
    
    return redirect('realizar_checkout', pk=pagamento.pk)

@login_required
def atualizar_status_pagamento(request, pk):
    if not (request.user.is_superuser or request.user.is_staff):
        messages.error(request, "Acesso negado.")
        return redirect('dashboard')
        
    pagamento = get_object_or_404(Pagamento, pk=pk)
    if request.method == 'POST':
        novo_status = request.POST.get('status')
        if novo_status in dict(Pagamento.STATUS_CHOICES):
            pagamento.status = novo_status
            pagamento.save()
            messages.success(request, f"Status do pagamento de {pagamento.usuario} atualizado para {pagamento.get_status_display()}.")
    
    # Redireciona de volta para onde veio (lista de usuários ou lista de pagamentos)
    return redirect(request.META.get('HTTP_REFERER', 'pagamento_list'))
