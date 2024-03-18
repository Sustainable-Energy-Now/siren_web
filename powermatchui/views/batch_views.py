#  batch_views.py
from siren_web.database_operations import fetch_included_technologies_data, fetch_demand_data
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.http import HttpResponse
from siren_web.models import Analysis, Scenarios, Technologies, variations  # Import the Scenario model
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
            variation_name = cleaned_data.get('variation_name', None)
            variation = cleaned_data.get('variation', None)
            
            updated_technologies = {}
            for idtechnology, values in technologies.items():
                dimension = cleaned_data.get(f'dimension_{idtechnology}', None)
                startval = values[1] if dimension == 'capacity' \
                else values[2] if dimension == 'multiplier' \
                else values[3] if dimension == 'capex' \
                else values[4] if dimension == 'fom' \
                else values[5] if dimension == 'vom' \
                else values[6] if dimension == 'lifetime' \
                else values[7]
                step = cleaned_data.get(f'step_{idtechnology}', None)
                if step:
                    updated_technologies[idtechnology] = [dimension, startval, step]
                    idtech = idtechnology
                    break

            # Create a new variation if variation_name is provided
            if variation_name:
                technology = Technologies.objects.get(idtechnologies=idtech)  # Get the first technology
                variation_description = \
                    f"A variation for {technology.technology_name} with {dimension} changed by {str(step)} over {str(iterations)} iterations."
                variation = variations.objects.create(
                    idtechnologies=technology,
                    variation_name=variation_name,
                    variation_description=variation_description,
                    dimension=dimension,
                    startval=startval,
                    step=step,
                    iterations=iterations,
                )
            # Process technologies dictionary as needed
            run_batch(request, demand_year, scenario, iterations, updated_technologies)
            success_message = "Batch run has completed."
            
    context = {
        'form': form, 'technologies': technologies,
        'demand_year': demand_year, 'scenario': scenario, 'success_message': success_message
        }
    return render(request, 'batch.html', context)

def clearScenario(id: int) -> None:
    Analysis.objects.filter(idScenarios=id).delete()
    
def run_batch(request, demand_year, scenario, iterations, updated_technologies) -> HttpResponse:
    # pmss_details, pmss_data, dispatch_order, re_order = fetch_demand_data(demand_year)
    option = 'B'
    # clearScenario(Scenario)
    # Iterate and call doDispatch
    sp_data, headers, sp_pts = submit_powermatch(demand_year, scenario, option, iterations, updated_technologies)
    success_message = 'Batch run has completed.'
    context = {
        'sp_data': sp_data, 'headers': headers, 'sp_pts': sp_pts,
        'success_message': success_message, 'demand_year': demand_year, 'scenario': scenario
    }
    return render(request, 'display_table.html', context)