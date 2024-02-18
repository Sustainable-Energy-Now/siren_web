from ..database_operations import fetch_generation_storage_data
from django.shortcuts import render
from django.http import HttpResponse
from ..models import Technologies # Import the Scenario model
from ..forms import MeritOrderForm

def set_merit_order(request):
    load_year = request.session.get('load_year')
    scenario = request.session.get('scenario')
    context = {}  # Initialize context with an empty dictionary
    success_message = ""
    
    if request.method == 'POST':
        # Handle form submission
        form = MeritOrderForm(request.POST)

        # Process form data
        #selected_scenario = form.cleaned_data['scenario']
        # Perform further actions with the selected scenario
        merit_order = request.POST.getlist('merit_order[]')
        excluded_resources = request.POST.getlist('excluded_resources[]')

        # Update the merit_order attribute for technologies in the 'Merit Order' column
        for index, tech_id in enumerate(merit_order, start=1):
            technology = Technologies.objects.get(idtechnologies=tech_id)
            technology.merit_order = index
            technology.save()

        # Update the merit_order attribute for technologies in the 'Excluded Resources' column
        for tech_id in excluded_resources:
            technology = Technologies.objects.get(idtechnologies=tech_id)
            technology.merit_order = 999
            technology.save()
        success_message = "Merit Order has been updated."

    form = MeritOrderForm()
    merit_order, excluded_resources = queryset= fetch_generation_storage_data(load_year)
    context = {'merit_order': merit_order, 'excluded_resources': excluded_resources, 'success_message': success_message, 'load_year': load_year, 'scenario': scenario}
    return render(request, 'merit_order.html', context)