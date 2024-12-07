# homes_views.py
from decimal import Decimal
from django.apps import apps
from django.contrib.auth.decorators import login_required
from django.db.models import Max
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from django.urls import path
from powermatchui.forms import DemandYearScenario
from powermatchui.views.exec_powermatch import submit_powermatch
from siren_web.database_operations import fetch_module_settings_data, fetch_scenario_settings_data
from siren_web.models import facilities
import json
import os

@login_required
def home(request):
    demand_year = request.session.get('demand_year', '')  # Get demand_year and scenario from session or default to empty string
    scenario= request.session.get('scenario', '')
    config_file = request.session.get('config_file')
    success_message = ""
    if request.method == 'POST':
        # Handle form submission
        demand_year_scenario = DemandYearScenario(request.POST)
        if demand_year_scenario.is_valid():
            demand_year = demand_year_scenario.cleaned_data['demand_year']
            request.session['demand_year'] = demand_year
            scenario = demand_year_scenario.cleaned_data['scenario']
            request.session['scenario'] = scenario # Assuming scenario is an instance of Scenarios
            success_message = "Settings updated."
    demand_year_scenario = DemandYearScenario()
    scenario_settings = {}
    if not demand_year:
        success_message = "Set the demand year and scenario in the home page first."
    else:
        scenario_settings = fetch_module_settings_data('Power')
        if not scenario_settings:
            scenario_settings = fetch_scenario_settings_data(scenario)
    # Query all facilities with latitude and longitude available
    facilities_data = facilities.objects.filter(latitude__isnull=False, longitude__isnull=False).values('facility_name', 'idtechnologies', 'latitude', 'longitude')
    # Convert the queryset to a list and then to JSON
    facilities_json = json.dumps(list(facilities_data))
    context = {
        'demand_year_scenario': demand_year_scenario,
        'demand_year': demand_year, 
        'scenario': scenario,
        'config_file': config_file,
        'success_message': success_message, 
        'facilities_json': facilities_json,
        }
    return render(request, 'powermapui_home.html', context)
