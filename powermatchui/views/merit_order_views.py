from siren_web.database_operations import fetch_merit_order_technologies
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.db.models import IntegerField
from django.shortcuts import render
from django.views.decorators.http import require_POST
from ..forms import MeritOrderForm
import json
from siren_web.models import Technologies # Import the Scenario model

@login_required
def set_merit_order(request):
    demand_year = request.session.get('demand_year')
    scenario = request.session.get('scenario')
    context = {}  # Initialize context with an empty dictionary
    success_message = ""
    merit_order = {}
    excluded_resources = {}
    
    if request.method == 'POST':
        # Handle form submission
        form = MeritOrderForm(request.POST)

        # Process form data
        #selected_scenario = form.cleaned_data['scenario']
        # Perform further actions with the selected scenario
        try:
            data = {}
            if request.body:
                data = json.loads(request.body)
            merit_order = data.get('meritOrderIds', [])
            excluded_resources = data.get('excludedResourcesIds', [])
        except Exception as e:
            print(f"Error saving order: {e}")

        # Process the IDs as needed, e.g., update the order of items in the database
        # Update the merit_order attribute for technologies in the 'Merit Order' column
        # Create a list of Cases to update the merit_order field based on tech_id

        for index, tech_id in enumerate(merit_order, start=1):
            Technologies.objects.filter(idtechnologies=tech_id).update(merit_order=index)
            # Update the merit_order attribute for technologies in the 'Excluded Resources' column
        for tech_id in excluded_resources:
            Technologies.objects.filter(idtechnologies=tech_id).update(merit_order=999)
        success_message = "Merit order saved successfully"

    form = MeritOrderForm()
    merit_order, excluded_resources = queryset= fetch_merit_order_technologies(demand_year)
    context = {'merit_order': merit_order, 'excluded_resources': excluded_resources, 'success_message': success_message, 'demand_year': demand_year, 'scenario': scenario}
    return render(request, 'merit_order.html', context)