from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.cache import cache
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
import json
from siren_web.database_operations import copy_technologies_from_year0, fetch_technology_by_id, fetch_merit_order_technologies
from siren_web.models import ScenariosTechnologies, Scenarios
from urllib.parse import urlencode

@login_required
def set_merit_order(request):
    if request.user.groups.filter(name='modellers').exists():
        pass
    else:
        messages.error(request, "Access not allowed.")
        return render(request, 'powermatchui_home.html')
    
    demand_year = request.session.get('demand_year')
    scenario = request.session.get('scenario')
    config_file = request.session.get('config_file')
    
    # Initialize with default values
    success_message = request.GET.get('success_message', '')
    merit_order = {}
    excluded_resources = {}
    
    if request.method == 'POST' and demand_year:
        scenario_obj = Scenarios.objects.get(title=scenario)
        
        # Process form data
        try:
            data = {}
            if request.body:
                data = json.loads(request.body)
            
            merit_order_ids = data.get('meritOrderIds', [])
            excluded_resources_ids = data.get('excludedResourcesIds', [])
        except Exception as e:
            messages.error(request, f"Error processing request: {e}")
            return JsonResponse({'status': 'error', 'message': str(e)})

        # Update the merit_order attribute for technologies in the 'Merit Order' column
        updated_count = 0
        for index, tech_id in enumerate(merit_order_ids, start=1):
            if tech_id:
                result = ScenariosTechnologies.objects.filter(
                    idtechnologies=tech_id, 
                    idscenarios=scenario_obj.pk
                ).update(merit_order=index)
                updated_count += result

        # Update the merit_order attribute for technologies in the 'Excluded Resources' column
        for index, tech_id in enumerate(excluded_resources_ids, start=800):
            if tech_id:
                technology = fetch_technology_by_id(tech_id)
                result = ScenariosTechnologies.objects.filter(
                    idtechnologies=tech_id, 
                    idscenarios=scenario_obj.pk
                ).update(merit_order=index)
                updated_count += result

        # Add success message using Django messages framework
        messages.success(request, f"Merit Order Updated. {updated_count} technologies updated.")
        
        # Return JSON response for AJAX
        return JsonResponse({'status': 'success', 'message': f'Merit Order Updated. {updated_count} technologies updated.'})
        
    # Always fetch the data for display
    if demand_year:
        scenario_obj = Scenarios.objects.get(title=scenario)
        idscenarios = scenario_obj.pk
        merit_order, excluded_resources = fetch_merit_order_technologies(idscenarios)
        
        if not len(merit_order) and not len(excluded_resources):
            success_message = "Reload the technologies."
    else:
        success_message = "Set a demand year, scenario and config first."
    
    context = {
        'merit_order': merit_order, 
        'excluded_resources': excluded_resources, 
        'success_message': success_message, 
        'demand_year': demand_year,
        'scenario': scenario,
        'config_file': config_file,
    }
    
    return render(request, 'merit_order.html', context)