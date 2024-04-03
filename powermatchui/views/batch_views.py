#  batch_views.py
from siren_web.database_operations import fetch_included_technologies_data, check_analysis_baseline
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.http import HttpResponse
from siren_web.models import Analysis, Scenarios, Technologies, variations  # Import the Scenario model
from ..forms import RunBatchForm, SelectVariationForm
from powermatchui.views.exec_powermatch import submit_powermatch

# Process form data
@login_required
def setup_variation(request):
    demand_year = request.session.get('demand_year')
    scenario = request.session.get('scenario')
    success_message = ""
    baseline = check_analysis_baseline(scenario)
    technologies= fetch_included_technologies_data(scenario)
    if not baseline:
        success_message = "Baseline the scenario first."

    if baseline and request.method == 'POST':
        # Handle form submission
        variation_name = request.POST.get('variation_name')
        variation = request.POST.get('variation')

        if variation_name and variation_name != 'new' and variation_name != 'Baseline':
            variation_inst = variations.objects.get(variation_name=variation_name)
            variation_data = {
                'variation_name': variation_name,
                'idtechnologies': variation_inst.idtechnologies,
                'iterations': variation_inst.iterations,
                'dimension': variation_inst.dimension,
                'step': variation_inst.step
            }
        else:  # Display technologies as is.
            variation_data = {
                'variation_name': variation_name,
            }
        variation_form = SelectVariationForm(selected_variation=variation_name)
        batch_form = RunBatchForm(technologies=technologies, variation_data=variation_data)
    else:
        variation_form = SelectVariationForm()
        batch_form = RunBatchForm(technologies=technologies)
            
    context = {
        'variation_form': variation_form,
        'batch_form': batch_form, 'technologies': technologies,
        'demand_year': demand_year, 'scenario': scenario, 'success_message': success_message
        }
    return render(request, 'batch.html', context)

def clearScenario(scenario_obj, variation_name) -> None:
    Analysis.objects.filter(idscenarios=scenario_obj,
                            variation=variation_name,
                            ).delete()
    
def run_batch(request) -> HttpResponse:
    if request.method == 'POST':
    # Handle form submission
        demand_year = request.session.get('demand_year')
        scenario = request.session.get('scenario')
        success_message = ""
        technologies= fetch_included_technologies_data(scenario)
        batch_form = RunBatchForm(request.POST, technologies=technologies)
        if batch_form.is_valid():
            cleaned_data = batch_form.cleaned_data
            iterations = cleaned_data['iterations']
            
            # Refresh the existing variation or create a new one if selected.
            variation_name = cleaned_data['variation_name']
            idtechnologies = cleaned_data['idtechnologies']
            dimension = cleaned_data['dimension']
            step = cleaned_data['step']
            technology = Technologies.objects.get(idtechnologies=idtechnologies)  # Get the first technology
            variation_gen_name = f"{technology.technology_signature}{dimension[:3]}{str(step)}.{str(iterations)}"
            variation_description = \
                f"A variation for {technology.technology_name} with {dimension} changed by {str(step)} over {str(iterations)} iterations."
            scenario_obj = Scenarios.objects.get(title=scenario)
            if dimension == 'capacity':
                startval = technology.capacity
            if variation_name == 'new':
                variation = variations.objects.create(
                idscenarios=scenario_obj,
                idtechnologies=technology,
                variation_name=variation_gen_name,
                variation_description=variation_description,
                dimension=dimension,
                startval=startval,
                step=step,
                iterations=iterations,
            )
            elif variation_name != 'Baseline':
                variation_inst = variations.objects.get(
                    variation_name=variation_name,
                    idscenarios=scenario_obj,
                    )
                variation_inst.idtechnologies = technology
                variation_inst.variation_description = variation_description
                variation_inst.variation_name = variation_gen_name
                variation_inst.dimension = dimension
                variation_inst.save()

                # pmss_details, pmss_data, dispatch_order, re_order = fetch_demand_data(demand_year)
                option = 'B'
                scenario_obj = Scenarios.objects.get(title=scenario)
                clearScenario(scenario_obj, variation_name)
                # Iterate and call doDispatch
                sp_data, headers, sp_pts = submit_powermatch(demand_year, scenario, option, iterations, variation_inst)
                success_message = 'Batch run has completed.'
                context = {
                    'sp_data': sp_data, 'headers': headers, 'sp_pts': sp_pts,
                    'success_message': success_message, 'demand_year': demand_year, 'scenario': scenario
                }
                return render(request, 'display_table.html', context)