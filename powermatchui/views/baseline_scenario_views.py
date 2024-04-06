# baseline_scenario_views.py
from django.db import transaction
from decimal import Decimal
from django.db.models import Sum
from django.contrib import messages
from django.shortcuts import render, redirect
from siren_web.database_operations import delete_analysis_scenario, fetch_analysis_scenario, \
    fetch_included_technologies_data, fetch_module_settings_data, fetch_scenario_settings_data, \
    fetch_technology_by_id, get_supply_by_technology
from siren_web.models import Demand, Generatorattributes, Technologies, Scenarios, ScenariosSettings, \
    ScenariosTechnologies, Settings, supplyfactors
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
            if (carbon_price != Decimal(scenario_settings['carbon_price'])):
                    scenario_settings['carbon_price'] = carbon_price
                    scenario_settings.save()
                    
            if (discount_rate != Decimal(scenarios_settings['discount_rate'])):
                    scenario_settings['discount_rate'] = discount_rate
                    scenario_settings.save()
                    
            for technology in technologies:
                capacity = baseline_form.cleaned_data.get(f'capacity_{idtechnologies}')
                if (technology.capacity != capacity):
                    technology.capacity = capacity
                    technology.save()

    else:
        if demand_year:
            scenario_obj = Scenarios.objects.get(title=scenario)
            analysis_list = fetch_analysis_scenario(scenario_obj)
            if analysis_list:
                if 'proceed' in request.GET:
                    if request.GET['proceed'] == 'Yes':
                        # Proceed with the rest of the GET function
                        # Your existing code here
                        pass
                    else:
                        # User chose not to proceed
                        messages.warning(request, "Operation canceled.")
                        return redirect('baseline_scenario')
                else:
                    # Render a template with the warning message
                    context = {
                        'demand_year': demand_year, 
                        'scenario': scenario, 
                        'success_message': success_message
                    }
                    return render(request, 'confirm_overwrite.html', context)
                
            total_supply_by_technology = \
                get_supply_by_technology(demand_year, scenario)
            
            delete_analysis_scenario(scenario_obj)
            technologies = {}
            technologies= fetch_included_technologies_data(scenario)
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
        runpowermatch_form = RunPowermatchForm(request.POST)
        scenario_obj = Scenarios.objects.get(title=scenario)

        if not demand_year:
            success_message = "Set the demand year and scenario first."
        elif runpowermatch_form.is_valid():
            level_of_detail = runpowermatch_form.cleaned_data['level_of_detail']
            save_baseline = runpowermatch_form.cleaned_data['save_baseline']
            option = level_of_detail[0]
            
            delete_analysis_scenario(scenario_obj)
            sp_output, headers, sp_pts = submit_powermatch(
                demand_year, scenario, 'S', 1, 
                None, save_baseline
                )
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