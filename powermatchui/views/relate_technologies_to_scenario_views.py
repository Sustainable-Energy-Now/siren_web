from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from ..forms import DemandYearScenario, RunPowermatchForm
from siren_web.database_operations import relate_technologies_to_scenario
from siren_web.models import Technologies, Scenarios, ScenariosTechnologies

@login_required
def relate_technologies(request):
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
            technologies = relate_technologies_to_scenario(idscenarios)
            for i, technology in enumerate(technologies, start=1):
                ScenariosTechnologies.objects.filter(idscenarios=idscenarios, idtechnologies=technology.pk).update(merit_order=i)
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