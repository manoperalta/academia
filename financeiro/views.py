from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Pagamento, Plano
from .forms import PagamentoForm
from datetime import date

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
            form.save()
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
