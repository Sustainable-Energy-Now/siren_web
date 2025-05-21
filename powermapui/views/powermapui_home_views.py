# homes_views.py
from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.db.models import Max
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from powermatchui.forms import DemandYearScenario
from siren_web.database_operations import fetch_module_settings_data, fetch_scenario_settings_data
from siren_web.models import facilities, Technologies, Zones
import json

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
        success_message = "Set a demand year, scenario and config first."
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

@login_required
@csrf_exempt
def add_facility(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            # Extract data from the request
            facility_name = data.get('facility_name')
            technology_id = data.get('technology_id')
            latitude = data.get('latitude')
            longitude = data.get('longitude')
            capacity = data.get('capacity')
            
            # Wind turbine specific fields
            turbine = data.get('turbine')
            hub_height = data.get('hub_height')
            no_turbines = data.get('no_turbines')
            tilt = data.get('tilt')
            
            # Validate required fields
            if not all([facility_name, technology_id, latitude, longitude]):
                return JsonResponse({'status': 'error', 'message': 'Missing required fields'}, status=400)
            
            # Get the technology object
            try:
                technology = Technologies.objects.get(pk=technology_id)
            except Technologies.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': 'Invalid technology ID'}, status=400)
            
            # Create a basic facility code based on name and technology
            tech_prefix = technology.technology_name[:3].upper() if technology.technology_name else "FAC"
            facility_code = f"{tech_prefix}_{facility_name.replace(' ', '_').lower()}"[:30]
            
            # Validate wind turbine specific fields if applicable
            wind_tech_ids = [15, 16, 17]  # Onshore, Offshore, Floating wind IDs
            if technology_id in wind_tech_ids:
                if not turbine:
                    return JsonResponse({'status': 'error', 'message': 'Turbine model is required for wind facilities'}, status=400)
                if not hub_height:
                    return JsonResponse({'status': 'error', 'message': 'Hub height is required for wind facilities'}, status=400)
                if not no_turbines or int(no_turbines) < 1:
                    return JsonResponse({'status': 'error', 'message': 'Number of turbines must be at least 1'}, status=400)
            
            # Create new facility
            new_facility = facilities(
                facility_name=facility_name,
                facility_code=facility_code,
                active=True,
                idtechnologies=technology,
                capacity=capacity or 0.0,
                latitude=latitude,
                longitude=longitude
            )
            
            # Add wind turbine specific fields if applicable
            if technology_id in wind_tech_ids:
                new_facility.turbine = turbine
                new_facility.hub_height = hub_height
                new_facility.no_turbines = no_turbines
                new_facility.tilt = tilt
            
            new_facility.save()
            
            # Get the technology name for the response
            tech_name = technology.technology_name
            
            return JsonResponse({
                'status': 'success',
                'message': f'{tech_name} facility added successfully',
                'facility_id': new_facility.idfacilities,
                'facility_name': new_facility.facility_name,
                'technology': tech_name
            })
            
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    
    # If not POST, return error
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)

# Add this function to get available technologies for the dropdown
@login_required
def get_technologies(request):
    techs = Technologies.objects.all().values('idtechnologies', 'technology_name')
    return JsonResponse(list(techs), safe=False)
