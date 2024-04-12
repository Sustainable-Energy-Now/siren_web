#  variations_views.py
from siren_web.database_operations import fetch_included_technologies_data, check_analysis_baseline
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.http import HttpResponse
from siren_web.models import Analysis, Scenarios, Technologies, variations  # Import the Scenario model
from ..forms import RunVariationForm, SelectVariationForm
from powermatchui.views.exec_powermatch import submit_powermatch

# Process form data
@login_required
def setup_variation(request):
    demand_year = request.session.get('demand_year')
    scenario = request.session.get('scenario')
    success_message = ""
    if demand_year:
        baseline = check_analysis_baseline(scenario)
        technologies= fetch_included_technologies_data(scenario)
        if not baseline:
            success_message = "Baseline the scenario first."
    else:
        technologies = {}
        baseline = None
        success_message = "Set the demand year and scenario in the home page first."

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
        variations_form = RunVariationForm(technologies=technologies, variation_data=variation_data)
    else:
        if demand_year:
            variation_form = SelectVariationForm()
            variations_form = RunVariationForm(technologies=technologies)
        else:
            variation_form = None
            variations_form = None
            
    context = {
        'variation_form': variation_form,
        'variations_form': variations_form, 'technologies': technologies,
        'demand_year': demand_year, 'scenario': scenario, 'success_message': success_message
        }
    return render(request, 'variations.html', context)

def clearScenario(scenario_obj, variation_name) -> None:
    Analysis.objects.filter(idscenarios=scenario_obj,
                            variation=variation_name,
                            ).delete()
    
def run_variations(request) -> HttpResponse:
    if request.method == 'POST':
    # Handle form submission
        demand_year = request.session.get('demand_year')
        scenario = request.session.get('scenario')
        success_message = ""
        technologies= fetch_included_technologies_data(scenario)
        variations_form = RunVariationForm(request.POST, technologies=technologies)
        if variations_form.is_valid():
            cleaned_data = variations_form.cleaned_data
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
            elif dimension == 'lifetime':
                startval = technology.lifetime
            if variation_name == 'new':
                try:
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
                except Exception as e:
                    success_message = 'Variation creation failed.'
                variation_name = variation_gen_name
            if variation_name != 'Baseline':
                variation_inst = variations.objects.get(
                    variation_name=variation_name,
                    idscenarios=scenario_obj,
                    )
                variation_inst.idtechnologies = technology
                variation_inst.variation_description = variation_description
                variation_inst.variation_name = variation_gen_name
                variation_inst.dimension = dimension
                variation_inst.step=step
                variation_inst.iterations=iterations
                variation_inst.save()

                option = 'S'
                scenario_obj = Scenarios.objects.get(title=scenario)
                clearScenario(scenario_obj, variation_name)
                # Iterate and call doDispatch
                save_data = True
                sp_output, headers, sp_pts = submit_powermatch(
                    demand_year, scenario, option, iterations, variation_inst,
                    save_data,
                    )
                sp_data = []
                for row in sp_output:
                    formatted_row = []
                    for item in row:
                        if isinstance(item, float):
                            formatted_row.append('{:,.2f}'.format(item))
                        else:
                            formatted_row.append(item)
                    sp_data.append(formatted_row)
                success_message = 'Create variations run has completed.'
                context = {
                    'sp_data': sp_data, 'headers': headers, 'sp_pts': sp_pts,
                    'success_message': success_message, 'demand_year': demand_year, 'scenario': scenario
                }
                return render(request, 'display_table.html', context)
    variation_name = request.POST.get('variation_name')
    variation_form = SelectVariationForm(selected_variation=variation_name)
    success_message = 'Select a variation and hit the Refresh button first.'
    context = {
        'variation_form': variation_form,
        'variations_form': variations_form, 'technologies': technologies,
        'demand_year': demand_year, 'scenario': scenario, 'success_message': success_message
        }
    return render(request, 'variations.html', context)