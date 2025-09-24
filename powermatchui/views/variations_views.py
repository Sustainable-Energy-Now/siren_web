#  variations_views.py
from siren_web.database_operations import fetch_technology_attributes, check_analysis_baseline, fetch_technology_by_id
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods
import json
from siren_web.models import Analysis, Scenarios, variations  # Import the Scenario model
from ..forms import CombinedVariationForm
from powermatchui.views.exec_powermatch import submit_powermatch_with_progress
from powermatchui.views.baseline_scenario_views import process_results_for_template

# Process form data
@login_required
def setup_variation(request):
    if not request.user.groups.filter(name='modellers').exists():
        success_message = "Access not allowed."
        context = {'success_message': success_message}
        return render(request, 'powermatchui_home.html', context)

    demand_year = request.session.get('demand_year')
    scenario = request.session.get('scenario')
    config_file = request.session.get('config_file')
    success_message = ""
    
    if not demand_year:
        success_message = "Set a demand year, scenario and config first."
        context = {'success_message': success_message}
        return render(request, 'variations.html', context)

    baseline = check_analysis_baseline(scenario)
    technologies = fetch_technology_attributes(demand_year, scenario)
    
    if not baseline:
        success_message = "Baseline the scenario first."
        context = {'success_message': success_message}
        return render(request, 'variations.html', context)

    # Prepare technologies data for JavaScript
    technologies_json = {}
    if technologies:
        for tech_name, tech_obj in technologies.items():
            technologies_json[tech_name] = {
                'tech_name': tech_obj.tech_name,
                'tech_signature': tech_obj.tech_signature,
                'tech_id': tech_obj.tech_id,
                'multiplier': float(tech_obj.multiplier) if tech_obj.multiplier else 0,
                'capex': float(tech_obj.capex) if tech_obj.capex else 0,
                'fixed_om': float(tech_obj.fixed_om) if tech_obj.fixed_om else 0,
                'variable_om': float(tech_obj.variable_om) if tech_obj.variable_om else 0,
                'lifetime': float(tech_obj.lifetime) if tech_obj.lifetime else 0,
            }

    scenario_obj = Scenarios.objects.get(title=scenario)
    
    if request.method == 'POST':
        # Handle form submission
        combined_form = CombinedVariationForm(
            request.POST, 
            scenario=scenario_obj, 
            technologies=technologies
        )
        
        if combined_form.is_valid():
            return handle_variation_submission(
                request, combined_form.cleaned_data, technologies, 
                demand_year, scenario, config_file
            )
        else:
            success_message = 'Please check the form for errors.'
    else:
        # Initial page load
        # Get the first variation if any exist for auto-selection
        initial_variation_data = None
        variations_queryset = variations.objects.filter(idscenarios=scenario_obj)
        if variations_queryset.exists():
            first_variation = variations_queryset.first()
            initial_variation_data = {
                'variation_name': first_variation.variation_name,
                'stages': first_variation.stages,
                'dimension': first_variation.dimension,
                'step': first_variation.step,
                'idtechnologies': {
                    'idtechnologies': first_variation.idtechnologies.pk if first_variation.idtechnologies else None
                }
            }
        
        combined_form = CombinedVariationForm(
            scenario=scenario_obj, 
            technologies=technologies,
            variation_data=initial_variation_data
        )
    
    context = {
        'combined_form': combined_form,
        'technologies': technologies,
        'technologies_json': json.dumps(technologies_json),
        'variation_data': json.dumps({}),  # For JavaScript compatibility
        'demand_year': demand_year,
        'scenario': scenario,
        'config_file': config_file,
        'success_message': success_message
    }
    return render(request, 'variations.html', context)

def handle_variation_submission(request, cleaned_data, technologies, demand_year, scenario, config_file):
    """Handle the form submission for creating/updating variations"""
    stages = cleaned_data['stages']
    variation_name = cleaned_data['variation_name']
    original_variation_name = cleaned_data.get('original_variation_name')
    idtechnologies = cleaned_data['idtechnologies']
    dimension = cleaned_data['dimension']
    step = cleaned_data['step']
    
    # Get technology object and details
    technology_obj = fetch_technology_by_id(idtechnologies)
    tech_name = None
    for key, tech in technologies.items():
        if str(tech.tech_id) == str(idtechnologies):
            tech_name = key
            technology = tech
            break
    
    if not tech_name:
        success_message = 'Technology not found.'
        return render_form_with_error(request, technologies, demand_year, scenario, config_file, success_message)
    
    # Generate variation details
    variation_gen_name = f"{technology.tech_signature}.{dimension[:3]}{str(step)}.{str(stages)}"
    variation_description = f"A variation for {technology.tech_name} with {dimension} changed by {str(step)} over {str(stages)} stages."
    scenario_obj = Scenarios.objects.get(title=scenario)
    
    # Get start value based on dimension
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
    else:
        startval = 0
        
    # Create or update variation
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
            return render_form_with_error(request, technologies, demand_year, scenario, config_file, success_message)
        variation_name = variation_gen_name
    else:
        # Update existing variation
        try:
            variation_inst = variations.objects.get(
                variation_name=original_variation_name or variation_name,
                idscenarios=scenario_obj,
            )
            variation_inst.idtechnologies = technology_obj[0]
            variation_inst.variation_description = variation_description
            variation_inst.variation_name = variation_gen_name
            variation_inst.dimension = dimension
            variation_inst.step = step
            variation_inst.stages = stages
            variation_inst.startval = startval
            variation_inst.save()
            variation_name = variation_gen_name
        except variations.DoesNotExist:
            success_message = 'Variation not found for update.'
            return render_form_with_error(request, technologies, demand_year, scenario, config_file, success_message)

    # Clear existing analysis data and run PowerMatch
    clearScenario(scenario_obj, variation_name)
    
    option = 'S'
    variation_inst = variations.objects.get(
        variation_name=variation_name,
        idscenarios=scenario_obj,
    )
    
    # Run the PowerMatch analysis
    dispatch_results, summary_report = submit_powermatch_with_progress(
        demand_year, scenario, option, stages,
        variation_inst, True, progress_handler=None
    )
    
    # Process data for display
    context = process_results_for_template(
        dispatch_results, scenario, True, 
        demand_year, config_file
    )
    success_message = 'Create variants run has completed.'
    return render(request, 'display_table.html', 
        {**context, 'summary_report': summary_report, 
         'success_message': success_message})

def render_form_with_error(request, technologies, demand_year, scenario, config_file, success_message):
    """Helper function to render the form with error messages"""
    scenario_obj = Scenarios.objects.get(title=scenario)
    combined_form = CombinedVariationForm(scenario=scenario_obj, technologies=technologies)
    
    # Prepare technologies data for JavaScript
    technologies_json = {}
    if technologies:
        for tech_name, tech_obj in technologies.items():
            technologies_json[tech_name] = {
                'tech_name': tech_obj.tech_name,
                'tech_signature': tech_obj.tech_signature,
                'tech_id': tech_obj.tech_id,
                'multiplier': float(tech_obj.multiplier) if tech_obj.multiplier else 0,
                'capex': float(tech_obj.capex) if tech_obj.capex else 0,
                'fixed_om': float(tech_obj.fixed_om) if tech_obj.fixed_om else 0,
                'variable_om': float(tech_obj.variable_om) if tech_obj.variable_om else 0,
                'lifetime': float(tech_obj.lifetime) if tech_obj.lifetime else 0,
            }
    
    context = {
        'combined_form': combined_form,
        'technologies': technologies,
        'technologies_json': json.dumps(technologies_json),
        'variation_data': json.dumps({}),
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
@require_http_methods(["POST"])
def get_variation_data(request):
    """AJAX endpoint to fetch variation data when a variant is selected"""
    try:
        data = json.loads(request.body)
        variation_name = data.get('variation_name')
        scenario = data.get('scenario')
        
        if not variation_name or not scenario:
            return JsonResponse({'success': False, 'error': 'Missing parameters'})
        
        if variation_name in ['new', 'Baseline']:
            return JsonResponse({
                'success': True,
                'variation': {
                    'variation_name': variation_name,
                    'variation_description': '',
                    'stages': '',
                    'dimension': '',
                    'step': '',
                    'idtechnologies': '',
                    'technology_details': ''
                }
            })
        
        try:
            scenario_obj = Scenarios.objects.get(title=scenario)
            variation_inst = variations.objects.get(
                variation_name=variation_name,
                idscenarios=scenario_obj
            )
            
            # Get technology details for accordion expansion
            technology_details = ""
            idtechnologies = ""
            if variation_inst.idtechnologies:
                technology_name = variation_inst.idtechnologies.technology_name
                technology_details = f"{technology_name} Details"
                idtechnologies = str(variation_inst.idtechnologies.pk)
            
            variation_data = {
                'variation_name': variation_inst.variation_name,
                'variation_description': variation_inst.variation_description,
                'stages': variation_inst.stages,
                'dimension': variation_inst.dimension,
                'step': str(variation_inst.step),
                'idtechnologies': idtechnologies,
                'technology_details': technology_details
            }
            
            return JsonResponse({'success': True, 'variation': variation_data})
            
        except variations.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Variation not found'})
        except Scenarios.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Scenario not found'})
            
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
