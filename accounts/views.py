from django.shortcuts import render, redirect
from django.contrib.auth import login
from .forms import CustomUserCreationForm
from usuarios.models import Usuario
from professores.models import Professor

def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user_type = form.cleaned_data.get('user_type')
            if user_type == 'professor':
                user.is_professor = True
            else:
                user.is_student = True
            user.save()
            
            # Criar perfil
            if user.is_professor:
                Professor.objects.create(user=user, nome=user.username) # Preenchendo nome com username inicialmente
            else:
                Usuario.objects.create(user=user, nome=user.username)

            login(request, user)
            if user.is_professor:
                return redirect('complete_profile_professor')
            else:
                return redirect('complete_profile')
    else:
        form = CustomUserCreationForm()
    return render(request, 'registration/register.html', {'form': form})
