from django.shortcuts import render
from django.urls import reverse

def siren_system_view(request):
    context = {
        'siren_system_view_url': reverse('siren_system_view')
    }

    # Handle the request
    return render(request, 'siren_system.html', context)

    table = request.POST.get('table')  # Get the title parameter from the request
    # Perform actions based on the table
    return HttpResponse('Action performed for ' + table)
