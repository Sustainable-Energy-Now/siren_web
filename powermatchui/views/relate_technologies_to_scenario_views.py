from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from ..forms import DemandYearScenario, RunPowermatchForm
from siren_web.database_operations import relate_technologies_to_scenario, fetch_Storage_IDs_list
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
        storage_technologies = fetch_Storage_IDs_list(demand_year)
        # Update existing records
        ScenariosTechnologies.objects.filter(
            idtechnologies__in=storage_technologies,
            idscenarios=idscenarios
        ).update(merit_order=999)
        
            # Create new records for technologies not present in ScenariosTechnologies
        existing_tech_ids = ScenariosTechnologies.objects.filter(
            idtechnologies__in=storage_technologies,
            idscenarios=idscenarios
        ).values_list('idtechnologies', flat=True)

        new_tech_ids = set(storage_technologies) - set(existing_tech_ids)
        new_records = [
            ScenariosTechnologies(idtechnologies_id=tech_id, idscenarios=scenario_obj, merit_order=999)
            for tech_id in new_tech_ids
        ]

        ScenariosTechnologies.objects.bulk_create(new_records)

    else:
        success_message = "Demand Year and Scenario must be specified."

    demand_year_scenario = DemandYearScenario()
    runpowermatch_form = RunPowermatchForm()

    context = {
        'demand_year_scenario': demand_year_scenario, 'runpowermatch_form': runpowermatch_form,
        'success_message': success_message, 'demand_year': demand_year, 'scenario': scenario
        }
    return render(request, 'powermatchui_home.html', context)