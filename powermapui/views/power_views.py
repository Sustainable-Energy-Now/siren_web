from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.http import HttpResponse
from siren_web.database_operations import fetch_facilities_scenario, fetch_included_technologies_data, \
    fetch_module_settings_data, fetch_scenario_settings_data
from powermapui.powermap.wascene import WAScene

@login_required
def generate_power(request):
    demand_year = request.session.get('demand_year', '')  # Get demand_year and scenario from session or default to empty string
    scenario= request.session.get('scenario', '')
    success_message = ""
    technologies = {}
    scenario_settings = {}
    if not demand_year:
        success_message = "Set the demand year and scenario in the home page first."
    else:
        technologies= fetch_included_technologies_data(scenario)
        scenario_settings = fetch_module_settings_data('Power')
        if not scenario_settings:
            scenario_settings = fetch_scenario_settings_data(scenario)
        facilities = fetch_facilities_scenario(scenario)
        scene = WAScene(facilities)
    if request.method == 'POST':
        context = {
            'success_message': success_message, 'demand_year': demand_year, 'scenario': scenario,
        }
        return render(request, 'table_update_page.html', context)
    else:
        context = {
            'success_message': success_message, 'demand_year': demand_year, 'scenario': scenario,
        }
        return render(request, 'table_update_page.html', context)