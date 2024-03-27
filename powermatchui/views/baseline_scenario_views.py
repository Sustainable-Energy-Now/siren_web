# baseline_scenario_views.py
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
                    
            if parameters_updated:
                delete_analysis_scenario(scenario_obj)

    else:
        if demand_year:
            scenario_obj = Scenarios.objects.get(title=scenario)
            analysis_list = fetch_analysis_scenario(scenario_obj)
            if analysis_list:
                success_message = "Existing baseline and variants will be overridden."
            carbon_price= scenario_settings['carbon_price']
            discount_rate= scenario_settings['discount_rate']
        baseline_form = BaselineScenarioForm(
            technologies=technologies, 
            carbon_price=carbon_price, 
            discount_rate=discount_rate)

    context = {
        'baseline_form': baseline_form,
        'runpowermatch_form': runpowermatch_form,
        'technologies': technologies,
        'scenario_settings': scenario_settings,
        'demand_year': demand_year, 'scenario': scenario, 'success_message': success_message
    }
    return render(request, 'baseline_scenario.html', context)

def run_baseline(request):
    demand_year = request.session.get('demand_year')
    scenario = request.session.get('scenario')
    success_message = ""
    if request.method == 'POST':
        scenario_obj = Scenarios.objects.get(title=scenario)
        runpowermatch_form = RunPowermatchForm()
        if not demand_year:
            success_message = "Set the demand year and scenario first."
        elif runpowermatch_form.is_valid():
            level_of_detail = runpowermatch_form.cleaned_data['level_of_detail']
            option = level_of_detail[0]
            
            delete_analysis_scenario(scenario_obj)
            sp_output, headers, sp_pts = submit_powermatch(demand_year, scenario, 'S', 1, None)
            sp_data = []
            for row in sp_output:
                formatted_row = []
                for item in row:
                    if isinstance(item, Decimal):
                        formatted_row.append('{:,.2f}'.format(item))
                    else:
                        formatted_row.append(item)
                sp_data.append(formatted_row)
                
            success_message = "Baseline re-established"
            context = {
                'sp_data': sp_data, 'headers': headers, 'sp_pts': sp_pts,
                'success_message': success_message, 'demand_year': demand_year, 'scenario': scenario
            }
            return render(request, 'display_table.html', context)
                
        else:
            technologies= fetch_included_technologies_data(scenario)
            baseline_form = BaselineScenarioForm(technologies=technologies)

            scenario_settings = {}
            scenario_settings = fetch_scenario_settings_data(scenario)
            context = {
                'baseline_form': baseline_form,
                'runpowermatch_form': runpowermatch_form,
                'technologies': technologies,
                'scenario_settings': scenario_settings,
                'demand_year': demand_year, 'scenario': scenario, 'success_message': success_message
            }
            return render(request, 'baseline_scenario.html', context)