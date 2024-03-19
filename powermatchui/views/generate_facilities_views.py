from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from ..forms import DemandYearScenario, RunPowermatchForm
from siren_web.database_operations import relate_technologies_to_scenario
from siren_web.models import facilities, Scenarios, ScenariosFacilities

@login_required
def generate_facilities(request):
    demand_year = request.session.get('demand_year', '')  # Get demand_year and scenario from session or default to empty string
    scenario= request.session.get('scenario', '')
    if scenario:
        try:
            scenario_obj = Scenarios.objects.get(title=scenario)
            idscenarios = scenario_obj.idscenarios
        except Scenarios.DoesNotExist:
            # Handle the case when no scenario with the given title is found
            idscenarios = None
            success_message = "The scenario does not exist."
            
        if idscenarios:
            facilities = relate_technologies_to_scenario(idscenarios)
            for i, facility in enumerate(facilities, start=1):
                ScenariosFacilities.objects.filter(idscenarios=idscenarios, idfacilities=facility.pk).update(merit_order=i)
            success_message = "Technologies related to Scenario."
    else:
        success_message = "Demand Year and Scenario must be specified."

    demand_year_scenario = DemandYearScenario()
    runpowermatch_form = RunPowermatchForm()

    context = {
        'demand_year_scenario': demand_year_scenario, 'runpowermatch_form': runpowermatch_form,
        'success_message': success_message, 'demand_year': demand_year, 'scenario': scenario
        }
    return render(request, 'powermatchui_home.html', context)