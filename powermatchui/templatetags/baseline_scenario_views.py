# baseline_scenario_views.py
from django.db import transaction
from decimal import Decimal
from siren_web.database_operations import delete_analysis_scenario, fetch_analysis_scenario, fetch_included_technologies_data, \
    fetch_module_settings_data, fetch_scenario_settings_data
from django.shortcuts import render
from siren_web.models import Technologies, Scenarios, ScenariosSettings, Settings
from ..forms import BaselineScenarioForm, RunPowermatchForm
from powermatchui.views.exec_powermatch import submit_powermatch

def baseline_scenario(request):
    demand_year = request.session.get('demand_year')
    scenario = request.session.get('scenario')
    success_message = ""
    technologies = {}
    scenario_settings = {}
    if not demand_year:
        success_message = "Set the demand year and scenario in the home page first."
    else:
        technologies= fetch_included_technologies_data(scenario)
        scenario_settings = fetch_module_settings_data('Powermatch')
        if not scenario_settings:
            scenario_settings = fetch_scenario_settings_data(scenario)
    baseline_form = BaselineScenarioForm(technologies=technologies)
    runpowermatch_form = RunPowermatchForm()

    if request.method == 'POST' and demand_year:
        baseline_form = BaselineScenarioForm(request.POST)
        if baseline_form.is_valid():
            carbon_price = baseline_form.cleaned_data.get('carbon_price')
            discount_rate = baseline_form.cleaned_data.get('discount_rate')
            parameters_updated = False
            if (carbon_price != Decimal(scenario_settings['carbon_price'])):
                    scenario_settings['carbon_price'] = carbon_price
                    scenario_settings.save()
                    parameters_updated = True
                    
            if (discount_rate != Decimal(scenarios_settings['discount_rate'])):
                    scenario_settings['discount_rate'] = discount_rate
                    scenario_settings.save()
                    parameters_updated = True


            with transaction.atomic():
                for technology in technologies:
                    capacity = baseline_form.cleaned_data.get(f'capacity_{technology.idtechnologies}')
                    if capacity is not None:
                        technology_obj, created = Technologies.objects.get_or_create(
                            idtechnologies=technology.idtechnologies,
                            year=demand_year,
                            defaults={
                                'technology_name': technology.technology_name,
                                'technology_signature': technology.technology_signature,
                                # ... (Copy other fields from the baseline Technology object)
                            }
                        )
                        if created:
                            # If a new row was created, copy the fields from the baseline Technology object
                            baseline_technology = Technologies.objects.get(idtechnologies=technology.idtechnologies, year=0)
                            technology_obj.image = baseline_technology.image
                            technology_obj.caption = baseline_technology.caption
                            # ... (Copy other fields from the baseline Technology object)
                            technology_obj.save()

                        if technology_obj.capacity != capacity:
                            technology_obj.capacity = capacity
                            technology_obj.save()
                            parameters_updated = True

                if parameters_updated:
                    delete_analysis_scenario(scenario_obj)

    # ...
    # Existing code
    # ...
