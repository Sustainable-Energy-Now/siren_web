# baseline_scenario_views.py
from django.contrib.auth.decorators import login_required
from decimal import Decimal
from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render, redirect
import numpy as np
from siren_web.database_operations import delete_analysis_scenario, fetch_analysis_scenario, \
    fetch_technologies_with_multipliers, fetch_module_settings_data, fetch_scenario_settings_data, update_scenario_settings_data
from siren_web.models import Demand, Generatorattributes, Technologies, Scenarios, ScenariosSettings, \
    ScenariosTechnologies
from typing import Dict, Any
from ..forms import BaselineScenarioForm, RunPowermatchForm
from .balance_grid_load import DispatchResults
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

            dispatch_results = submit_powermatch(
                demand_year, scenario, option, 1, 
                None, save_baseline
                )
            sp_output = dispatch_results.summary_data
            metadata = dispatch_results.metadata
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
                # Prepare headers for display
                header_mapping = {
                    'capacity_mw': 'Capacity',
                    'generation_mwh': 'Generation',
                    'to_meet_load_mwh': 'To Meet Load',
                    'capacity_factor': 'CF',
                    'annual_cost': 'Cost',
                    'lcog_per_mwh': 'LCOG Cost',
                    'lcoe_per_mwh': 'LCOE Cost',
                    'emissions_tco2e': 'Emissions',
                    'emissions_cost': 'Emissions Cost',
                    'lcoe_with_co2_per_mwh': 'LCOE with CO2 Cost',
                    'max_generation_mw': 'Max Generation',
                    'max_balance': 'Max Balance',
                    'capital_cost': 'Capital Cost',
                    'lifetime_cost': 'Lifetime Cost',
                    'lifetime_emissions': 'Lifetime Emissions',
                    'lifetime_emissions_cost': 'Lifetime Emissions Cost',
                    'area_km2': 'Area km²',
                    'reference_lcoe': 'Reference LCOE',
                    'reference_cf': 'Reference CF'
                }
                original_headers = list(sp_output.dtype.names)
                readable_headers = []
                for header in original_headers:
                    readable_headers.append(header_mapping.get(header, header))
                # Convert structured array to list of lists
                sp_data_list = []
                for row in sp_output:
                    row_data = []
                    for field in original_headers:
                        value = row[field]
                        # Check if value is numeric and round to 2 decimal places
                        if isinstance(value, (int, float, np.number)):
                            row_data.append(round(float(value), 2))
                        else:
                            row_data.append(value)
                    sp_data_list.append(row_data)
                # Create the summary report
                summary_report = create_summary_report(scenario, dispatch_results)
                context = {
                    'sp_data': sp_data_list, 'headers': readable_headers,
                    'summary_report': summary_report,
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

def create_summary_report(scenario, dispatch_results: DispatchResults) -> Dict[str, Any]:
    """Create a comprehensive summary report from dispatch results"""
    summary = dispatch_results.summary_data
    metadata = dispatch_results.metadata
    
    # System overview
    system_overview = {
        'total_load_gwh': metadata['total_load_mwh'] / 1000,
        'load_met_percentage': metadata['load_met_pct'] * 100,
        'renewable_percentage': metadata['renewable_pct'] * 100,
        'renewable_load_percentage': metadata['renewable_load_pct'] * 100,
        'storage_contribution_percentage': metadata['storage_pct'] * 100,
        'curtailment_percentage': metadata['curtailment_pct'] * 100,
        'system_lcoe_per_mwh': metadata['system_lcoe'],
        'system_lcoe_with_co2_per_mwh': metadata['system_lcoe_with_co2']
    }
    
    # Technology breakdown
    technology_breakdown = []
    for record in summary:
        tech_data = {
            'technology': record['technology'],
            'capacity_mw': record['capacity_mw'],
            'generation_gwh': record['generation_mwh'] / 1000,
            'capacity_factor_pct': record['capacity_factor'] * 100,
            'lcoe_per_mwh': record['lcoe_per_mwh'],
            'emissions_ktco2e': record['emissions_tco2e'] / 1000,
            'area_km2': record['area_km2']
        }
        technology_breakdown.append(tech_data)
    
    # Economic summary
    economic_summary = {
        'total_annual_cost_millions': metadata['system_totals']['total_annual_cost'] / 1e6,
        'total_capital_cost_millions': metadata['system_totals']['total_capital_cost'] / 1e6,
        'total_lifetime_cost_millions': metadata['system_totals']['total_lifetime_cost'] / 1e6,
        'carbon_price_per_tco2e': metadata['carbon_price'],
        'discount_rate_pct': metadata['discount_rate'] * 100
    }
    
    # Environmental summary
    environmental_summary = {
        'total_emissions_ktco2e_per_year': metadata['system_totals']['total_emissions_tco2e'] / 1000,
        'total_emissions_cost_millions_per_year': metadata['system_totals']['total_emissions_cost'] / 1e6,
        'lifetime_emissions_mtco2e': metadata['system_totals']['total_lifetime_emissions'] / 1e6,
        'total_land_use_km2': metadata['system_totals']['total_area_km2']
    }
    
    return {
        'system_overview': system_overview,
        'technology_breakdown': technology_breakdown,
        'economic_summary': economic_summary,
        'environmental_summary': environmental_summary,
        'processing_metadata': {
            'simulation_year': metadata['year'],
            'scenario_name': scenario
        }
    }
