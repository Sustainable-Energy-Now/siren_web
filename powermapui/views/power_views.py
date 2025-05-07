from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.http import HttpResponse
from siren_web.database_operations import fetch_full_facilities_data, \
    fetch_module_settings_data, fetch_scenario_settings_data, fetch_all_config_data
from siren_web.models import capacities, facilities
from powermapui.views.wasceneweb import WASceneWeb as WAScene
from powermapui.views.powermodelweb import PowerModelWeb as PowerModel

@login_required
def generate_power(request):
    demand_year = request.session.get('demand_year', '')  # Get demand_year and scenario from session or default to empty string
    scenario= request.session.get('scenario', '')
    config_file = request.session.get('config_file')
    success_message = ""
    technologies = {}
    scenario_settings = {}
    if not demand_year:
        success_message = "Set a demand year, scenario and config first."
    else:
        scenario_settings = fetch_module_settings_data('Powermap')
        if not scenario_settings:
            scenario_settings = fetch_scenario_settings_data(scenario)
        facilities_list = fetch_full_facilities_data(demand_year, scenario)
        config = fetch_all_config_data(request)
        scene = WAScene(config, facilities_list)
        power = PowerModel(config, scene._stations.stations, demand_year, scenario_settings)
        generated = power.getValues()
        for station in power.stations:
            try:
                if (power.ly[station.name]):
                    facility_obj = facilities.objects.get(facility_code=station.name)
                    for index, interval in enumerate(power.ly[station.name]):          
                    # for generation in power.ly: 
                        capacities.objects.create(
                            idfacilities=facility_obj,
                            year=demand_year,
                            hour=index,
                            quantum=interval
                        )
            except:
                pass
        
    if request.method == 'POST':
        context = {
            'demand_year': demand_year,
            'scenario': scenario,
            'config_file': config_file,
            'success_message': success_message,
        }
        return render(request, 'table_update_page.html', context)
    else:
        context = {
            'demand_year': demand_year,
            'scenario': scenario,
            'config_file': config_file,
            'success_message': success_message,
        }
        return render(request, 'table_update_page.html', context)