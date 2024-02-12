from ..database_operations import fetch_constraints_data, fetch_demand_data, fetch_settings_data,  fetch_technologies_data
from decimal import Decimal
from django.apps import apps
from django.db.models import Max
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from django.urls import path
from ..forms import LoadYearForm
from ..models import Constraints, Demand, Scenarios, Settings, Generators, Zones
from ..powermatch import pmcore as pm
from ..powermatch.pmcore import Optimisation, Facility, PM_Facility
from ..tasks import run_powermatch_task


def main(request):
    if request.method == 'POST':
        form = LoadYearForm(request.POST)
        if form.is_valid():
            load_year = form.cleaned_data['load_year']
            level_of_detail = form.cleaned_data['level_of_detail']
            # Perform necessary actions with the selected load year
            settings = fetch_settings_data(request)
            constraints = fetch_constraints_data(request)
            generators, dispatch_order, re_order = fetch_technologies_data(request, load_year)
            ex = pm.powerMatch(settings=settings, constraints=constraints, generators=generators)
            pmss_data, pmss_details = fetch_demand_data(request, load_year)
            option = level_of_detail[0]
            pm_data_file = 'G:/Shared drives/SEN Modelling/modelling/SWIS/Powermatch_data_actual.xlsx'
            data_file = 'Powermatch_results_actual.xlsx'
            df_message = ex.doDispatch(load_year, option, pmss_details, pmss_data, re_order, dispatch_order,
                pm_data_file, data_file, title=None)
            print(df_message)
            return HttpResponse("Submission successful!")
    else:
        form = LoadYearForm()
    return render(request, 'main.html', {'form': form})

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

