from django.shortcuts import render

def login_view(request):
    return render(request, 'guest/login.html')

def register_view(request):
    return render(request, 'guest/register.html')