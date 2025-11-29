from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Usuario
from .forms import UsuarioForm, UsuarioProfileForm

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

@login_required
def complete_profile(request):
    # Tenta obter o perfil do usuário logado
    try:
        usuario = request.user.usuario_profile
    except Usuario.DoesNotExist:
        # Se não existir (o que não deveria acontecer pelo fluxo de registro), cria um
        usuario = Usuario.objects.create(user=request.user, nome=request.user.username)

    if request.method == 'POST':
        form = UsuarioProfileForm(request.POST, request.FILES, instance=usuario)
        if form.is_valid():
            form.save()
            messages.success(request, 'Perfil completado com sucesso!')
            return redirect('dashboard')
    else:
        form = UsuarioProfileForm(instance=usuario)
    
    return render(request, 'usuarios/complete_profile.html', {'form': form})
