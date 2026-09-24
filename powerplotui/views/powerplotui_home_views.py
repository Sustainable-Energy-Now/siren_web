from django.contrib.auth.decorators import login_required
from django.shortcuts import render

@login_required
def powerplotui_home(request):
    return render(request, 'powerplotui_home.html')
