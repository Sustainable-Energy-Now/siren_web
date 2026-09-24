from django.contrib.auth.decorators import login_required
from django.shortcuts import render

@login_required
def powermatchui_home(request):
    return render(request, 'powermatchui_home.html')
