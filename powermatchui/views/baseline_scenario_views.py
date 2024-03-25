# baseline_scenario_views.py
from decimal import Decimal
from siren_web.database_operations import delete_analysis_scenario, fetch_included_technologies_data, \
    fetch_module_settings_data, fetch_scenario_settings_data
from django.shortcuts import render
from siren_web.models import Technologies, Scenarios, ScenariosSettings, Settings
from ..forms import BaselineScenarioForm
from ..views import exec_powermatch as ex_pm

def baseline_scenario(request):
    demand_year = request.session.get('demand_year')
    scenario = request.session.get('scenario')
    success_message = ""
    technologies= fetch_included_technologies_data(scenario)
    form = BaselineScenarioForm(technologies=technologies)
    scenario_settings = {}
    scenario_settings = fetch_module_settings_data('Powermatch')
    if not scenario_settings:
        scenario_settings = fetch_scenario_settings_data(scenario)

    if request.method == 'POST':
        baseline_form = BaselineScenarioForm(request.POST)
        if form.is_valid():
            carbon_price = form.cleaned_data.get('carbon_price')
            discount_rate = form.cleaned_data.get('discount_rate')
            parameters_updated = False
            if (carbon_price != Decimal(scenarios_settings['carbon_price'])):
                    scenarios_settings['carbon_price'] = carbon_price
                    scenarios_settings.save()
                    parameters_updated = True
                    
            if (discount_rate != Decimal(scenarios_settings['discount_rate'])):
                    scenarios_settings['discount_rate'] = discount_rate
                    scenarios_settings.save()
                    parameters_updated = True
                    
            for technology in technologies:
                capacity = form.cleaned_data.get(f'capacity_{idtechnologies}')
                if (technology.capacity != capacity):
                    technology.capacity = capacity
                    technology.save()
                    parameters_updated = True

    else:
        carbon_price= scenario_settings['carbon_price']
        discount_rate= scenario_settings['discount_rate']
        baseline_form = BaselineScenarioForm(
            technologies=technologies, 
            carbon_price=carbon_price, 
            discount_rate=discount_rate)

    context = {
        'baseline_form': baseline_form,
        'technologies': technologies,
        'scenario_settings': scenario_settings,
        'demand_year': demand_year, 'scenario': scenario, 'success_message': success_message
    }
    return render(request, 'baseline_scenario.html', context)

def run_baseline(request):
    demand_year = request.session.get('demand_year')
    scenario = request.session.get('scenario')
    success_message = ""
    scenario_obj = Scenarios.objects.get(title=scenario)
    delete_analysis_scenario(scenario_obj)
    ex_pm.submit_powermatch(demand_year, scenario, 'S', 1, None)

    success_message = "Baseline re-established"
    technologies= fetch_included_technologies_data(scenario)
    baseline_form = BaselineScenarioForm(technologies=technologies)
    scenario_settings = {}
    scenario_settings = fetch_scenario_settings_data(scenario)
    context = {
        'baseline_form': baseline_form,
        'technologies': technologies,
        'scenario_settings': scenario_settings,
        'demand_year': demand_year, 'scenario': scenario, 'success_message': success_message
    }
    return render(request, 'baseline_scenario.html', context)