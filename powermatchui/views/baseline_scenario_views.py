# baseline_scenario_views.py
from django.contrib.auth.decorators import login_required
from decimal import Decimal
from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render, redirect
from siren_web.database_operations import delete_analysis_scenario, fetch_analysis_scenario, \
    fetch_technologies_with_multipliers, fetch_module_settings_data, fetch_scenario_settings_data, update_scenario_settings_data
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
    config_file = request.session.get('config_file')
    success_message = ""
    technologies = {}
    scenario_settings = {}
    
    if not demand_year:
        success_message = "Set a demand year and scenario first."
    else:
        technologies = fetch_technologies_with_multipliers(scenario)
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
            
            # Update carbon price if changed
            if (carbon_price != Decimal(scenario_settings['carbon_price'])):
                update_scenario_settings_data(scenario, 'Powermatch', 'carbon price', carbon_price)
                    
            # Update discount rate
            if (discount_rate != Decimal(scenario_settings['discount_rate'])):
                update_scenario_settings_data(scenario, 'Powermatch', 'discount rate', discount_rate)
            
            success_message = "No changes were made."
            
            # Update technology multipliers
            for technology in technologies:
                idtechnologies = technology.idtechnologies
                multiplier_key = f"multiplier_{idtechnologies}"
                new_multiplier = cleaned_data.get(multiplier_key)
                
                try:
                    # Get the ScenariosTechnologies instance
                    scenario_tech = ScenariosTechnologies.objects.get(
                        idscenarios__title=scenario,
                        idtechnologies=technology
                    )
                    
                    if scenario_tech.mult != float(new_multiplier):
                        # Update the multiplier on ScenariosTechnologies
                        scenario_tech.mult = float(new_multiplier)
                        scenario_tech.save()
                        success_message = "Runtime parameters updated."
                        
                except ScenariosTechnologies.DoesNotExist:
                    # Handle case where technology is not in scenario
                    messages.warning(request, f"Technology {technology.technology_name} not found in scenario {scenario}")
                    continue
                except ValueError:
                    # Handle invalid multiplier values
                    messages.error(request, f"Invalid multiplier value for {technology.technology_name}")
                    continue
                    
        else:
            # Handle form errors and display specific messages for multiplier fields
            for field_name, errors in baseline_form.errors.items():
                if field_name.startswith('multiplier_'):
                    tech_id = field_name.replace('multiplier_', '')
                    # Find the technology name for better error messaging
                    tech_name = "Unknown"
                    for tech in technologies:
                        if str(tech.pk) == tech_id:
                            tech_name = tech.technology_name
                            break
                    for error in errors:
                        messages.error(request, f"Multiplier error for {tech_name}: {error}")
                elif field_name in ['carbon_price', 'discount_rate']:
                    for error in errors:
                        messages.error(request, f"{field_name.replace('_', ' ').title()}: {error}")
                else:
                    # Handle any other field errors
                    for error in errors:
                        messages.error(request, f"{field_name}: {error}")
            
            # Render the form with errors
            technologies = fetch_technologies_with_multipliers(scenario)
            scenario_settings = fetch_scenario_settings_data(scenario)
            if not scenario_settings:
                scenario_settings = fetch_module_settings_data('Powermatch')

            carbon_price = scenario_settings.get('carbon_price', None)
            discount_rate = scenario_settings.get('discount_rate', None)

            context = {
                'baseline_form': baseline_form,
                'runpowermatch_form': RunPowermatchForm(),
                'technologies': technologies,
                'scenario_settings': scenario_settings,
                'demand_year': demand_year,
                'scenario': scenario,
                'config_file': config_file,
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
                        'config_file': config_file,
                        'success_message': success_message
                    }
                    return render(request, 'confirm_overwrite.html', context)
            
    # Prepare form data for display
    if demand_year:
        technologies = fetch_technologies_with_multipliers(scenario)
        carbon_price = scenario_settings.get('carbon_price', None)
        discount_rate = scenario_settings.get('discount_rate', None)
    else:
        technologies = {}
        carbon_price = None
        discount_rate = None
        
    baseline_form = BaselineScenarioForm(
        technologies=technologies, 
        carbon_price=carbon_price, 
        discount_rate=discount_rate
    )

    context = {
        'baseline_form': baseline_form,
        'runpowermatch_form': runpowermatch_form,
        'technologies': technologies,
        'scenario_settings': scenario_settings,
        'demand_year': demand_year, 
        'scenario': scenario,
        'config_file': config_file,
        'success_message': success_message
    }
    return render(request, 'baseline_scenario.html', context)

def run_baseline(request):
    demand_year = request.session.get('demand_year')
    scenario = request.session.get('scenario')
    config_file = request.session.get('config_file')
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
            
            results = submit_powermatch(
                request, demand_year, scenario, option, 1, 
                None, save_baseline
                )
            sp_output = results
            
            if option == 'D':
                data_file = f"{scenario}-baseline detailed results"
                response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                response['Content-Disposition'] = f"attachment; filename={data_file}.xlsx"
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
                
                headers = ['Technology', 'Capacity\n(Gen, MW;\nStor, MWh)', 'To meet\nLoad (MWh)',
                    'Subtotal\n(MWh)', 'CF', 'Cost ($/yr)', 'LCOG\nCost\n($/MWh)', 'LCOE\nCost\n($/MWh)',
                    'Emissions\n(tCO2e)', 'Emissions\nCost', 'LCOE With\nCO2 Cost\n($/MWh)', 'Max.\nMWH',
                    'Max.\nBalance', 'Capital\nCost', 'Lifetime\nCost', 'Lifetime\nEmissions',
                    'Lifetime\nEmissions\nCost', 'Area (km^2)', 'Reference\nLCOE', 'Reference\nCF']
                sp_pts = []
                context = {
                    'sp_data': sp_data, 'headers': headers, 'sp_pts': sp_pts,
                    'success_message': success_message,
                    'demand_year': demand_year,
                    'scenario': scenario,
                    'config_file': config_file,
                }
                return render(request, 'display_table.html', context)
                
        technologies = fetch_technologies_with_multipliers(scenario)
        baseline_form = BaselineScenarioForm(technologies=technologies)

        scenario_settings = fetch_scenario_settings_data(scenario)
        context = {
            'baseline_form': baseline_form,
            'runpowermatch_form': runpowermatch_form,
            'technologies': technologies,
            'scenario_settings': scenario_settings,
            'demand_year': demand_year,
            'scenario': scenario,
            'config_file': config_file,
            'success_message': success_message
        }
        return render(request, 'baseline_scenario.html', context)