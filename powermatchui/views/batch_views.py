#  batch_views.py
from siren_web.database_operations import fetch_included_technologies_data, fetch_demand_data
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.http import HttpResponse
from siren_web.models import Analysis, Scenarios  # Import the Scenario model
from ..forms import RunBatchForm
from powermatchui.views.exec_powermatch import submit_powermatch

# Process form data
@login_required
def setup_batch(request):
    demand_year = request.session.get('demand_year')
    scenario = request.session.get('scenario')
    success_message = ""
    technologies= fetch_included_technologies_data(demand_year)
    form = RunBatchForm(technologies=technologies)
    if request.method == 'POST':
        # Handle form submission
        form = RunBatchForm(request.POST, technologies=technologies)
        if form.is_valid():
            cleaned_data = form.cleaned_data
            iterations = cleaned_data['iterations']
            updated_technologies = {}
            for key in cleaned_data:
                if key.startswith('capacity_'):
                    idtechnology = key.replace('capacity_', '')
                    capacity = cleaned_data[f'multiplier_{idtechnology}']
                    mult = cleaned_data[f'multiplier_{idtechnology}']
                    step = cleaned_data.get(f'step_{idtechnology}', None)
                    updated_technologies[idtechnology] = [capacity, mult, step]
            # Process technologies dictionary as needed
            run_batch(demand_year, scenario, iterations, updated_technologies)
            success_message = "Batch Parameters have been updated."
            
    context = {
        'form': form, 'technologies': technologies,
        'demand_year': demand_year, 'scenario': scenario, 'success_message': success_message
        }
    return render(request, 'batch.html', context)

def clearScenario(id: int) -> None:
    Analysis.objects.filter(idScenarios=id).delete()
    
def run_batch(demand_year, scenario, iterations, updated_technologies) -> None:
    # pmss_details, pmss_data, dispatch_order, re_order = fetch_demand_data(demand_year)
    option = 'B'
    # clearScenario(Scenario)
    # Iterate and call doDispatch
    sp_data, headers, sp_pts = submit_powermatch(demand_year, scenario, option, iterations, updated_technologies)
    context = {
        'sp_data': sp_data, 'headers': headers, 'sp_pts': sp_pts,
        'success_message': success_message, 'demand_year': demand_year, 'scenario': scenario
    }
    return render(request, 'display_table.html', context)