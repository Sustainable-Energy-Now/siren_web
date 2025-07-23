#  variations_views.py
from siren_web.database_operations import fetch_technology_attributes, check_analysis_baseline, fetch_technology_by_id
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.http import HttpResponse
from siren_web.models import Analysis, Scenarios, variations  # Import the Scenario model
from ..forms import RunVariationForm, SelectVariationForm
from powermatchui.views.exec_powermatch import submit_powermatch_with_progress
from powermatchui.views.baseline_scenario_views import process_results_for_template

# Process form data
@login_required
def setup_variation(request):
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
    if demand_year:
        baseline = check_analysis_baseline(scenario)
        technologies= fetch_technology_attributes(demand_year, scenario)
        if not baseline:
            success_message = "Baseline the scenario first."
    else:
        technologies = {}
        baseline = None
        success_message = "Set a demand year, scenario and config first."

    if baseline and request.method == 'POST':
        # Handle form submission
        variation_name = request.POST.get('variation_name')
        variation = request.POST.get('variation')

        if variation_name and variation_name != 'new' and variation_name != 'Baseline':
            variation_inst = variations.objects.get(variation_name=variation_name)
            variation_data = {
                'variation_name': variation_name,
                'idtechnologies': variation_inst.idtechnologies,
                'stages': variation_inst.stages,
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
            scenario_obj = Scenarios.objects.get(title=scenario)
            variation_form = SelectVariationForm(scenario=scenario_obj)
            variations_form = RunVariationForm(technologies=technologies)
        else:
            variation_form = None
            variations_form = None
            
    context = {
        'variation_form': variation_form,
        'variations_form': variations_form,
        'technologies': technologies,
        'demand_year': demand_year,
        'scenario': scenario,
        'config_file': config_file,
        'success_message': success_message
        }
    return render(request, 'variations.html', context)

def clearScenario(scenario_obj, variation_name) -> None:
    Analysis.objects.filter(idscenarios=scenario_obj,
                            variation=variation_name,
                            ).delete()
@login_required
def run_variations(request) -> HttpResponse:
    if request.method == 'POST':
    # Handle form submission
        demand_year = request.session.get('demand_year')
        scenario = request.session.get('scenario')
        config_file = request.session.get('config_file')
        success_message = ""
        technologies= fetch_technology_attributes(demand_year, scenario)
        variations_form = RunVariationForm(request.POST, technologies=technologies)
        if variations_form.is_valid():
            cleaned_data = variations_form.cleaned_data
            stages = cleaned_data['stages']
            
            # Refresh the existing variation or create a new one if selected.
            variation_name = cleaned_data['variation_name']
            idtechnologies = cleaned_data['idtechnologies']
            technology_obj = fetch_technology_by_id(idtechnologies)
            tech_name = technology_obj[0].technology_name
            dimension = cleaned_data['dimension']
            step = cleaned_data['step']
            technology = technologies[tech_name]
            variation_gen_name = f"{technology.tech_signature}{dimension[:3]}{str(step)}.{str(stages)}"
            variation_description = \
                f"A variation for {technology.tech_name} with {dimension} changed by {str(step)} over {str(stages)} stages."
            scenario_obj = Scenarios.objects.get(title=scenario)
            if dimension == 'multiplier':
                startval = technology.multiplier
            elif dimension == 'capex':
                startval = technology.capex
            elif dimension == 'fom':
                startval = technology.fixed_om
            elif dimension == 'vom':
                startval = technology.variable_om
            elif dimension == 'lifetime':
                startval = technology.lifetime
            if variation_name == 'new':
                try:
                    variation = variations.objects.create(
                        idscenarios=scenario_obj,
                        idtechnologies=technology_obj[0],
                        variation_name=variation_gen_name,
                        variation_description=variation_description,
                        dimension=dimension,
                        startval=startval,
                        step=step,
                        stages=stages,
                    )
                except Exception as e:
                    success_message = 'Variation creation failed.'
                variation_name = variation_gen_name
            if variation_name != 'Baseline':
                variation_inst = variations.objects.get(
                    variation_name=variation_name,
                    idscenarios=scenario_obj,
                    )
                variation_inst.idtechnologies = technology_obj[0]
                variation_inst.variation_description = variation_description
                variation_inst.variation_name = variation_gen_name
                variation_inst.dimension = dimension
                variation_inst.step=step
                variation_inst.stages=stages
                variation_inst.save()

                option = 'S'
                scenario_obj = Scenarios.objects.get(title=scenario)
                clearScenario(scenario_obj, variation_name)
                # Iterate and call powerMatch
                dispatch_results = submit_powermatch_with_progress(
                    demand_year, scenario, option, stages,
                    variation_inst, True, progress_handler=None
                )
                # Process data for display
                context = process_results_for_template(
                    dispatch_results, scenario, True, 
                    demand_year, request.session.get('config_file')
                )
                success_message = 'Create variants run has completed.'
                return render(request, 'display_table.html', context)
            
    variation_name = request.POST.get('variation_name')
    variation_form = SelectVariationForm(selected_variation=variation_name)
    success_message = 'Select a variation and hit the Refresh button first.'
    context = {
        'variation_form': variation_form,
        'variations_form': variations_form, 'technologies': technologies,
        'demand_year': demand_year,
        'scenario': scenario,
        'config_file': config_file,
        'success_message': success_message
        }
    return render(request, 'variations.html', context)