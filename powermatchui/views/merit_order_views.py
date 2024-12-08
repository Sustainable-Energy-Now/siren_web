from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
import json
from siren_web.database_operations import copy_technologies_from_year0, fetch_merit_order_technologies
from siren_web.models import Technologies, ScenariosTechnologies, Scenarios
from urllib.parse import urlencode

@login_required
def set_merit_order(request):
    if request.user.groups.filter(name='modellers').exists():
        pass
    else:
        success_message = "Access not allowed."
        context = {
            'success_message': success_message,
        }
        return render(request, 'powermatchui_home.html', context)
    demand_year = request.session.get('demand_year')
    scenario = request.session.get('scenario')
    config_file = request.session.get('config_file')
    context = {}  # Initialize context with an empty dictionary
    # Access the context data passed from the redirect
    success_message = request.GET.get('success_message', '')
    merit_order = {}
    excluded_resources = {}
    
    if (request.method == 'POST' and demand_year):
        scenario_obj = Scenarios.objects.get(title=scenario)
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
                Tech_new = copy_technologies_from_year0(technology.technology_name, demand_year, scenario)
                ScenariosTechnologies.objects.filter(idtechnologies=Tech_new, idscenarios=scenario_obj.pk).update(merit_order=index)

        # Update the merit_order attribute for technologies in the 'Excluded Resources' column
        for index, tech_id in enumerate(excluded_resources, start=800):
            if tech_id:
                technology = Technologies.objects.get(idtechnologies=tech_id)
                ScenariosTechnologies.objects.filter(idtechnologies=technology, idscenarios=scenario_obj.pk).update(merit_order=index)

        # Redirect back to the merit order view
        success_message = "Merit Order Updated."
        context = {
            'success_message': success_message,
        }
        # query_string = urlencode(context)
        # redirect_url = f"{reverse('merit_order')}?{query_string}"
        # return redirect(redirect_url)
        
    if not demand_year:
        success_message = "Set a demand year, scenario and config first."
    else:
        scenario_obj = Scenarios.objects.get(title=scenario)
        idscenarios = scenario_obj.pk
        merit_order, excluded_resources = fetch_merit_order_technologies(idscenarios)
        if not len(merit_order) and not len(excluded_resources):
            success_message = "Reload the technologies."
            
    context = {
        'merit_order': merit_order, 
        'excluded_resources': excluded_resources, 
        'success_message': success_message, 
        'demand_year': demand_year,
        'scenario': scenario,
        'config_file': config_file,
    }
    return render(request, 'merit_order.html', context)