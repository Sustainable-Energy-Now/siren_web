from siren_web.database_operations import fetch_merit_order_technologies
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
import json
from siren_web.models import Technologies, ScenariosTechnologies, Scenarios

@login_required
def set_merit_order(request):
    demand_year = request.session.get('demand_year')
    scenario = request.session.get('scenario')
    context = {}  # Initialize context with an empty dictionary
    success_message = ""
    merit_order = {}
    excluded_resources = {}
    scenario_obj = Scenarios.objects.get(title=scenario)
    
    if request.method == 'POST':
        # Process form data
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
        for index, tech_id in enumerate(merit_order, start=1):
            if tech_id:
                technology = Technologies.objects.get(idtechnologies=tech_id)
                ScenariosTechnologies.objects.filter(idtechnologies=technology, idscenarios=scenario_obj.pk).update(merit_order=index)

        # Update the merit_order attribute for technologies in the 'Excluded Resources' column
        for index, tech_id in enumerate(excluded_resources, start=800):
            if tech_id:
                technology = Technologies.objects.get(idtechnologies=tech_id)
                ScenariosTechnologies.objects.filter(idtechnologies=technology, idscenarios=scenario_obj.pk).update(merit_order=index)

        success_message = "Merit order saved successfully"
    idscenarios = scenario_obj.pk
    merit_order, excluded_resources = fetch_merit_order_technologies(demand_year, idscenarios)
    context = {'merit_order': merit_order, 'excluded_resources': excluded_resources, 'success_message': success_message, 'demand_year': demand_year, 'scenario': scenario}
    return render(request, 'merit_order.html', context)