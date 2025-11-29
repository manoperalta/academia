from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Pagamento, Plano, GatewayConfig
from .forms import PagamentoForm
from datetime import date
from .pagbank_service import PagBankService
import logging

logger = logging.getLogger(__name__)

@login_required
def pagamento_list(request):
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
