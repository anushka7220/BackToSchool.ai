from django.shortcuts import render, redirect
from django.contrib import messages
from .forms import UserRegisterForm, UserUpdateForm, ProfileUpdateForm
from django.contrib.auth.models import User
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required

def register(requests):
    if requests.method == 'POST':
        form = UserRegisterForm(requests.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            messages.success(requests, f'Your Account has been created! You are now abe to Log In')
            return redirect('login')
    else:
        form = UserRegisterForm()
    return render(requests, 'users/register.html', {'form': form})

def logout_view(request):
    logout(request)
    return render(request, 'users/logout.html')

@login_required
def profile(request):
    if request.method == 'POST':
        u_form = UserUpdateForm(request.POST, instance=request.user)
        p_form = ProfileUpdateForm(request.POST, request.FILES, instance=request.user.profile)       
        if u_form.is_valid() and p_form.is_valid():
            u_form.save()
            p_form.save()
            messages.success(request, f'Your Account has been updated!')
            return redirect('profile')
    else:
        u_form = UserUpdateForm(instance=request.user)
        p_form = ProfileUpdateForm(instance=request.user.profile)       
    context = {
        'u_form': u_form,
        'p_form': p_form    
    }
    return render(request, 'users/profile.html', context)

