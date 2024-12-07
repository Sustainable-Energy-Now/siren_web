from django.shortcuts import render
from siren_web.models import facilities, Scenarios, ScenariosFacilities

def facilities_list(request):
    demand_year = request.session.get('demand_year', '')  # Get demand_year and scenario from session or default to empty string
    scenario= request.session.get('scenario', '')
    config_file = request.session.get('config_file', '')
    success_message = ""
    scenarios = Scenarios.objects.all()

    # Filter facilities by scenario
    selected_scenario = request.GET.get('scenario')
    if selected_scenario:
        scenario_obj = Scenarios.objects.get(idscenarios=selected_scenario)
        facility_ids = ScenariosFacilities.objects.filter(idscenarios=scenario_obj).values_list('idfacilities', flat=True)
        facs = facilities.objects.filter(idfacilities__in=facility_ids)
    else:
        facs = facilities.objects.all()

    context = {
        'facilities': facs,
        'scenarios': scenarios,
        'selected_scenario': int(selected_scenario) if selected_scenario else None,
        'demand_year': demand_year,
        'scenario': scenario,
        'success_message': success_message,
        'config_file': config_file,
    }
    return render(request, 'facilities_list.html', context)