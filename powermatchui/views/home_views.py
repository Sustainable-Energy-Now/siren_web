# homes_views.py
from ..database_operations import fetch_constraints_data, fetch_demand_data, fetch_scenarios_data, fetch_settings_data,  fetch_full_generator_storage_data
from decimal import Decimal
from django.apps import apps
from django.contrib.auth.decorators import login_required
from django.db.models import Max
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from django.urls import path
from ..forms import HomeForm, RunPowermatchForm
from ..models import Constraints, Demand, Scenarios, Settings, Generators, Zones
from ..powermatch import pmcore as pm
from ..powermatch.pmcore import Facility, Optimisation, PM_Facility, powerMatch

@login_required
def home(request):
    load_year = request.session.get('load_year', '')  # Get load_year and scenario from session or default to empty string
    scenario= request.session.get('scenario', '')
    success_message = ""
    if request.method == 'POST':
        # Handle form submission
        home_form = HomeForm(request.POST)
        if home_form.is_valid():
            load_year = home_form.cleaned_data['load_year']
            request.session['load_year'] = load_year
            scenario = home_form.cleaned_data['scenario']
            request.session['scenario'] = scenario # Assuming scenario is an instance of Scenarios
            success_message = "Settings updated."
    else:
        home_form = HomeForm()
        runpowermatch_form = RunPowermatchForm()

    context = {
        'home_form': home_form, 'runpowermatch_form': runpowermatch_form,
        'success_message': success_message, 'load_year': load_year, 'scenario': scenario
        }
    return render(request, 'home.html', context)

def run_powermatch(request):
    load_year = request.session.get('load_year', '')  # Get load_year and scenario from session or default to empty string
    scenario= request.session.get('scenario', '')
    success_message = ""
    if request.method == 'POST':
        runpowermatch_form = RunPowermatchForm(request.POST)
        if runpowermatch_form.is_valid():
            level_of_detail = runpowermatch_form.cleaned_data['level_of_detail']
        
            settings = fetch_settings_data(request)
            constraints = fetch_constraints_data(request)
            if 'generators' in request.session:
                generators = request.session['generators']
                dispatch_order = request.session['dispatch_order']
                re_order = request.session['re_order']
            else:
                generators_result, column_names= fetch_full_generator_storage_data(request, load_year)
                generators = {}
                dispatch_order = []
                re_order = ['Load']
                pmss_details = {}
                # Process the results
                for generator_row in generators_result:
                    # Create a dictionary to store the attributes by name
                    attributes_by_name = {}
                    for i, value in enumerate(generator_row):
                        attributes_by_name[column_names[i]] = value

                    name = attributes_by_name['technology_name']
                    if name not in generators:
                        generators[name] = {}
                    generators[name] = Facility(
                        generator_name=name, capacity=attributes_by_name['capacity'], constr=attributes_by_name['technology_name'],
                        emissions=attributes_by_name['emissions'], initial=attributes_by_name['initial'], order=attributes_by_name['merit_order'], 
                        capex=attributes_by_name['capex'], fixed_om=attributes_by_name['FOM'], variable_om=attributes_by_name['VOM'],
                        fuel=attributes_by_name['fuel'], lifetime=attributes_by_name['lifetime'], disc_rate=attributes_by_name['discount_rate'],
                        lcoe=None, lcoe_cfs=None )
        
                    dispatchable=attributes_by_name['dispatchable']
                    if (dispatchable):
                        if (name not in dispatch_order):
                            dispatch_order.append(name)
                    renewable = attributes_by_name['renewable']
                    category = attributes_by_name['category']
                    if (renewable and category != 'Storage'):
                        if (name not in re_order):
                            re_order.append(name)
                    capacity = attributes_by_name['capacity']
                    if name not in pmss_details: # type: ignore
                        pmss_details[name] = PM_Facility(name, name, capacity, 'S', -1, 1)
                    else:
                        pmss_details[name].capacity = capacity

            # ex = pm.powerMatch(settings=settings, constraints=constraints, generators=generators)
            pmss_data, pmss_details, dispatch_order, re_order = fetch_demand_data(request, load_year)
            # Call the static method directly

            option = level_of_detail[0]
            pm_data_file = 'G:/Shared drives/SEN Modelling/modelling/SWIS/Powermatch_data_actual.xlsx'
            data_file = 'Powermatch_results_actual.xlsx'
            # df_message = ex.doDispatch(load_year, option, pmss_details, pmss_data, re_order, dispatch_order,
            #     pm_data_file, data_file, title=None)
            df_message = powerMatch.doDispatch(load_year, option, pmss_details, pmss_data, re_order, 
                dispatch_order,
                pm_data_file, data_file, title=None)
        else:
            home_form = HomeForm()
            runpowermatch_form = RunPowermatchForm()
        context = {
            'home_form': home_form,'runpowermatch_form': runpowermatch_form,
            'success_message': success_message, 'load_year': load_year, 'scenario': scenario
            }
        return render(request, 'home.html', context)
            
def start_powermatch_task(request):
    # Start the Celery task asynchronously
    task = run_powermatch_task.delay(settings, constraints, generators, load_year, option, pmss_details, pmss_data, re_order, dispatch_order, pm_data_file, data_file)
    return JsonResponse({'task_id': task.id})

def get_task_progress(request, task_id):
    # Get progress of the Celery task
    task = run_powermatch_task.AsyncResult(task_id)
    if task.state == 'SUCCESS':
        return JsonResponse({'progress': 100, 'message': 'Task completed successfully'})
    elif task.state == 'FAILURE':
        return JsonResponse({'progress': 0, 'message': 'Task failed'})
    else:
        # Get task progress from task.info dictionary (if available)
        progress = task.info.get('progress', 0)
        message = task.info.get('message', 'Task in progress')
        return JsonResponse({'progress': progress, 'message': message})
