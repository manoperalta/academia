from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Usuario
from .forms import UsuarioForm

@login_required
def usuario_list(request):
    usuarios = Usuario.objects.all()
    return render(request, 'usuarios/usuario_list.html', {'usuarios': usuarios})

@login_required
def usuario_create(request):
    if request.method == 'POST':
        form = UsuarioForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Usuário criado com sucesso!')
            return redirect('usuario_list')
    else:
        form = UsuarioForm()
    return render(request, 'usuarios/usuario_form.html', {'form': form, 'title': 'Novo Usuário'})

@login_required
def usuario_update(request, pk):
    usuario = get_object_or_404(Usuario, pk=pk)
    if request.method == 'POST':
        form = UsuarioForm(request.POST, instance=usuario)
        if form.is_valid():
            form.save()
            messages.success(request, 'Usuário atualizado com sucesso!')
            return redirect('usuario_list')
    else:
        form = UsuarioForm(instance=usuario)
    return render(request, 'usuarios/usuario_form.html', {'form': form, 'title': 'Editar Usuário'})

@login_required
def usuario_delete(request, pk):
    usuario = get_object_or_404(Usuario, pk=pk)
    if request.method == 'POST':
        usuario.delete()
        messages.success(request, 'Usuário excluído com sucesso!')
        return redirect('usuario_list')
    return render(request, 'usuarios/usuario_confirm_delete.html', {'usuario': usuario})
