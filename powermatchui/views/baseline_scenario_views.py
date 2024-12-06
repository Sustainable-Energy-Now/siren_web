# baseline_scenario_views.py
from django.contrib.auth.decorators import login_required
from decimal import Decimal
from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render, redirect
from siren_web.database_operations import delete_analysis_scenario, fetch_analysis_scenario, \
    fetch_included_technologies_data, fetch_module_settings_data, fetch_scenario_settings_data, update_scenario_settings_data
from siren_web.models import Demand, Generatorattributes, Technologies, Scenarios, ScenariosSettings, \
    ScenariosTechnologies, Settings, supplyfactors
from ..forms import BaselineScenarioForm, RunPowermatchForm
from powermatchui.views.exec_powermatch import submit_powermatch

@login_required
def baseline_scenario(request):
    if request.user.groups.filter(name='modellers').exists():
        pass
    else:
        success_message = "Access not allowed."
        context = {
            'success_message': success_message,
        }
        return render(request, 'powermatchui_home.html', context)
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
        baseline_form = BaselineScenarioForm(request.POST, technologies=technologies)
        if baseline_form.is_valid():
            cleaned_data = baseline_form.cleaned_data
            carbon_price = cleaned_data.get('carbon_price')
            discount_rate = cleaned_data.get('discount_rate')
            if (carbon_price != Decimal(scenario_settings['carbon_price'])):
                    update_scenario_settings_data(scenario, 'Powermatch', 'carbon price', carbon_price)
                    
            if (discount_rate != Decimal(scenario_settings['discount_rate'])):
                    update_scenario_settings_data(scenario, 'Powermatch', 'carbon price', discount_rate)
            success_message = "No changes were made."
            for technology in technologies:
                idtechnologies = technology.idtechnologies
                tech_key = f"capacity_{idtechnologies}"
                capacity = cleaned_data.get(tech_key)
                if (technology.capacity != float(capacity)):
                    technology.capacity = float(capacity)
                    technology.save()
                    success_message = "Runtime parameters updated."
        else:
            # Render the form with errors
            technologies = fetch_included_technologies_data(scenario)
            scenario_settings = fetch_module_settings_data('Powermatch')
            if not scenario_settings:
                scenario_settings = fetch_scenario_settings_data(scenario)

            carbon_price = scenario_settings.get('carbon_price', None)
            discount_rate = scenario_settings.get('discount_rate', None)

            context = {
                'baseline_form': baseline_form,
                'runpowermatch_form': RunPowermatchForm(),
                'technologies': technologies,
                'scenario_settings': scenario_settings,
                'demand_year': demand_year,
                'scenario': scenario,
                'success_message': 'Correct errors and resubmit.',
            }
            return render(request, 'baseline_scenario.html', context)
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
                        return redirect('powermatchui_home')
                else:
                    # Render a template with the warning message
                    context = {
                        'demand_year': demand_year, 
                        'scenario': scenario, 
                        'success_message': success_message
                    }
                    return render(request, 'confirm_overwrite.html', context)
            
    if demand_year:
        technologies= fetch_included_technologies_data(scenario)
        carbon_price= scenario_settings['carbon_price']
        discount_rate= scenario_settings['discount_rate']
    else:
        technologies = {}
        carbon_price= None
        discount_rate = None
        
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

def run_baseline(request: HttpRequest):
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
            
            if save_baseline:
                delete_analysis_scenario(scenario_obj)
            sp_output, headers, sp_pts = submit_powermatch(
                demand_year, scenario, option, 1, 
                None, save_baseline
                )
            if option == 'D':
                data_file = f"{scenario}-baseline detailed results"
                response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                response['Content-Disposition'] = f"attachment; filename={data_file}.xlsx"
                sp_output.save(response)
                return response
            else:
                sp_data = []
                for row in sp_output:
                    formatted_row = []
                    for item in row:
                        if isinstance(item, float):
                            formatted_row.append('{:,.2f}'.format(item))
                        else:
                            formatted_row.append(item)
                    sp_data.append(formatted_row)
                if save_baseline:
                    success_message = "Baseline re-established"
                else:
                    success_message = "Baseline run complete"
                context = {
                    'sp_data': sp_data, 'headers': headers, 'sp_pts': sp_pts,
                    'success_message': success_message, 'demand_year': demand_year, 'scenario': scenario
                }
                return render(request, 'display_table.html', context)
                
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