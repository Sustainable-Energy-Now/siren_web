from decimal import Decimal
from siren_web.database_operations import fetch_all_settings_data, fetch_generators_parameter, \
    fetch_included_technologies_data, fetch_module_settings_data, fetch_scenario_settings_data, \
    fetch_optimisation_data, fetch_supplyfactors_data, update_scenario_settings_data
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render
from django.http import HttpResponse
from siren_web.models import Scenarios, ScenariosSettings, Settings, Optimisations  # Import the Scenario model
from ..forms import OptimisationForm
from ..powermatch.pmcore import Facility, PM_Facility, powerMatch

def home(request):
    scenarios = Scenarios.objects.all()  # Retrieve all scenarios from the database
    return render(request, 'home.html', {'scenarios': scenarios})

def clear_scenario(request, scenario_id):
    # Logic to clear scenario with the given ID from the database
    return HttpResponse("Scenario has been cleared.")  # Return a response indicating success

def check_update_single_settings(scenario, cleaned_data, scenario_settings, parameter):
    if (cleaned_data.get(parameter) != scenario_settings[parameter]):
        update_scenario_settings_data(scenario, 'Optimisation', parameter, cleaned_data.get(parameter))

def check_update_triple_settings(scenario, scenario_settings, weight, better, worse, parameter):
    new_value = str(weight) + ',' + str(better) + ',' + str(worse)
    if (new_value != scenario_settings[parameter]):
        update_scenario_settings_data(scenario, 'Optimisation', parameter, new_value)

# Process form data
@login_required
def optimisation(request):
    demand_year = request.session.get('demand_year')
    scenario = request.session.get('scenario')
    success_message = ""
    technologies = {}
    scenario_settings = {}
    if not demand_year:
        success_message = "Set the demand year and scenario in the home page first."
    else:
        scenario_settings = fetch_module_settings_data('Optimisation')
        if not scenario_settings:
            scenario_settings = fetch_scenario_settings_data(scenario)
        technologies = fetch_included_technologies_data(scenario)
        optimisation_data = fetch_optimisation_data(scenario)
        if not optimisation_data:
            # If no optimisation data found, populate it using the capacities from technologies
            optimisation_data = {}
            for technology in technologies:
                optimisation_instance = Optimisations(
                    idscenarios=Scenarios.objects.get(idscenarios=scenario),
                    idtechnologies=technology,
                    capacity=technology.capacity
                )
                optimisation_data.append(optimisation_instance)
        optimisationform = OptimisationForm(scenario_settings=scenario_settings, optimisation_data=optimisation_data)

        if request.method == 'POST':
            # Handle form submission
            optimisationform = OptimisationForm(request.POST, scenario_settings=scenario_settings, optimisation_data=optimisation_data)
            if optimisationform.is_valid():
                # Process form data
                cleaned_data = optimisationform.cleaned_data
                for parameter in [
                    'choice', 'optGenn', 'mutation', 
                    'optPopn', 'stop', 'optLoad', 'optMutn', 'optStop'
                    ]:
                    check_update_single_settings(
                        scenario,
                        scenario_settings,
                        cleaned_data,
                        parameter
                    )
                check_update_triple_settings(
                    scenario,
                    scenario_settings,
                    cleaned_data.get('LCOE_Weight'), 
                    cleaned_data.get('LCOE_Better'), 
                    cleaned_data.get('LCOE_Worse'), 
                    'lcoe')
                check_update_triple_settings(
                    scenario,
                    scenario_settings,
                    cleaned_data.get('LCOE_Weight'), 
                    cleaned_data.get('LCOE_Better'), 
                    cleaned_data.get('LCOE_Worse'), 
                    'lcoe')
                check_update_triple_settings(
                    scenario,
                    scenario_settings,
                    cleaned_data.get('Load_Weight'), 
                    cleaned_data.get('Load_Better'), 
                    cleaned_data.get('Load_Worse'), 
                    'load_pct')
                check_update_triple_settings(
                    scenario,
                    scenario_settings,
                    cleaned_data.get('Surplus_Weight'), 
                    cleaned_data.get('Surplus_Better'), 
                    cleaned_data.get('Surplus_Worse'), 
                    'surplus')
                check_update_triple_settings(
                    scenario,
                    scenario_settings,
                    cleaned_data.get('RE_Weight'), 
                    cleaned_data.get('RE_Better'), 
                    cleaned_data.get('RE_Worse'), 
                    're_pct')
                check_update_triple_settings(
                    scenario,
                    scenario_settings,
                    cleaned_data.get('cost_Weight'), 
                    cleaned_data.get('cost_Better'), 
                    cleaned_data.get('cost_Worse'), 
                    'cost')
                check_update_triple_settings(
                    scenario,
                    scenario_settings,
                    cleaned_data.get('co2_Weight'), 
                    cleaned_data.get('co2_Better'), 
                    cleaned_data.get('co2_Worse'), 
                    'co2')
            for optimisation in optimisation_data:
                tech_key = f"{optimisation.idtechnologies.pk}"
                if (
                    cleaned_data.get(f'capacity_{tech_key}') != optimisation.capacity or
                    cleaned_data.get(f'capacitymax_{tech_key}') != optimisation.capacitymax or
                    cleaned_data.get(f'capacitymin_{tech_key}') != optimisation.capacitymin or
                    cleaned_data.get(f'capacitystep_{tech_key}') != optimisation.capacitystep
                ):
                    optimisation.capacity = cleaned_data.get(f'capacity_{tech_key}')
                    optimisation.capacitymax = cleaned_data.get(f'capacitymax_{tech_key}')
                    optimisation.capacitymin = cleaned_data.get(f'capacitymin_{tech_key}')
                    optimisation.capacitystep = cleaned_data.get(f'capacitystep_{tech_key}')
                    optimisation.save()
                
            success_message = "Optimisation Parameters have been updated."

    context = {'optimisationform': optimisationform, 'technologies': technologies, 'demand_year': demand_year, 'scenario': scenario,'success_message': success_message}
    return render(request, 'optimisation.html', context)

def run_optimisation(request):
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
    if request.method == 'POST':
        option = 'O'
        settings = fetch_all_settings_data()
        pmss_data, pmss_details, max_col = \
            fetch_supplyfactors_data(demand_year)
        generators, dispatch_order, re_order, pmss_details = fetch_generators_parameter(demand_year, scenario, pmss_details, max_col)

        scenario_obj = Scenarios.objects.get(title=scenario)
        opt_settings_data = ScenariosSettings.objects.filter(
            Q(idscenarios=scenario_obj) & Q(sw_context='Optimisation')
        ).values('parameter', 'value')
        OptParms = {setting['parameter']: setting['value'] for setting in opt_settings_data}
        optimisation_data = fetch_optimisation_data(scenario)
        message = powerMatch.optClicked(
            settings, demand_year, option, pmss_details, pmss_data, generators, re_order, 
            dispatch_order, OptParms, optimisation_data, None, None
        )

    context = {
        'demand_year': demand_year, 
        'scenario': scenario,
        'success_message': success_message}
    return render(request, 'optimisation.html', context)
