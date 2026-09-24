from django.contrib.auth.decorators import login_required
from django.shortcuts import render

@login_required
def powermapui_home(request):
    return render(request, 'powermapui_home.html')
