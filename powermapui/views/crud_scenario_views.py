from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.forms import modelformset_factory
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from ..forms import ScenarioForm
from siren_web.models import Scenarios, facilities, ScenariosFacilities
import json

def display_scenario(request):
    demand_year = request.session.get('demand_year')
    scenario = request.session.get('scenario')
    config_file = request.session.get('config_file')
    all_scenarios = Scenarios.objects.all()
    all_facilities = facilities.objects.all()
    scenario_form = ScenarioForm(request.POST or None)
    facility_formset = modelformset_factory(ScenariosFacilities, fields=('idfacilities',), extra=0)

    if request.method == 'POST':
        formset = facility_formset(request.POST, queryset=ScenariosFacilities.objects.none())
        if scenario_form.is_valid() and formset.is_valid():
            scenario = scenario_form.save()
            scenario_facilities = formset.save(commit=False)
            for sf in scenario_facilities:
                sf.idscenarios = scenario
                sf.save()  # This will trigger signals
    else:
        formset = facility_formset(queryset=ScenariosFacilities.objects.none())

    checkbox_status = {}
    for facility in all_facilities:
        checkbox_status[facility.idfacilities] = {}
        for scenario_obj in all_scenarios:
            checkbox_status[facility.idfacilities][scenario_obj.idscenarios] = ScenariosFacilities.objects.filter(idfacilities=facility, idscenarios=scenario_obj).exists()

    context = {
        'scenario_form': scenario_form,
        'facility_formset': facility_formset,
        'all_scenarios': all_scenarios,
        'all_facilities': all_facilities,
        'checkbox_status': checkbox_status,
        'demand_year': demand_year,
        'scenario': scenario,
        'config_file': config_file,
    }
    return render(request, 'create_scenario.html', context)

def update_scenario(request):
    demand_year = request.session.get('demand_year')
    scenario = request.session.get('scenario')
    config_file = request.session.get('config_file')
    all_scenarios = Scenarios.objects.all()
    all_facilities = facilities.objects.all()
    scenario_form = ScenarioForm(request.POST or None)
    facility_formset = modelformset_factory(ScenariosFacilities, fields=('idfacilities',), extra=0)

    if request.method == 'POST':
        for scenario_obj in all_scenarios:
            # Skip updating if this is the 'Current' scenario
            if scenario_obj.title == 'Current':
                continue
            
            facility_ids = [int(fid) for fid in request.POST.getlist(f'scenario_{scenario_obj.pk}_facilities')]
            scenario_facilities = ScenariosFacilities.objects.filter(idscenarios=scenario_obj)
            
            # Remove facilities that are not in the submitted list (one by one to trigger signals)
            facilities_to_remove = scenario_facilities.exclude(idfacilities__in=facility_ids)
            for facility_relation in facilities_to_remove:
                facility_relation.delete()  # This triggers signals properly
            
            # Add facilities that are in the submitted list but not in the database
            existing_facility_ids = set(scenario_facilities.values_list('idfacilities', flat=True))
            new_facility_ids = set(facility_ids) - existing_facility_ids
            
            # Create new relationships one by one to trigger signals
            for facility_id in new_facility_ids:
                try:
                    facility_obj = facilities.objects.get(pk=facility_id)
                    ScenariosFacilities.objects.create(
                        idscenarios=scenario_obj,
                        idfacilities=facility_obj
                    )  # This triggers post_save signal
                except facilities.DoesNotExist:
                    continue  # Skip invalid facility IDs
            
    checkbox_status = {}
    for facility in all_facilities:
        checkbox_status[facility.idfacilities] = {}
        for scenario_obj in all_scenarios:
            checkbox_status[facility.idfacilities][scenario_obj.idscenarios] = ScenariosFacilities.objects.filter(idfacilities=facility, idscenarios=scenario_obj).exists()
    
    messages.success(request, 'Successfully updated scenario facilities.')
    
    context = {
        'scenario_form': scenario_form,
        'facility_formset': facility_formset,
        'all_scenarios': all_scenarios,
        'all_facilities': all_facilities,
        'checkbox_status': checkbox_status,
        'demand_year': demand_year,
        'scenario': scenario,
        'config_file': config_file,
    }
    return render(request, 'create_scenario.html', context)

def edit_scenario(request, scenario_id):
    """
    View to edit an existing scenario's title and description.
    """
    scenario = get_object_or_404(Scenarios, pk=scenario_id)
    
    # Protect 'Current' scenario from editing
    if scenario.title == 'Current':
        messages.error(request, 'The "Current" scenario cannot be edited.')
        return redirect('powermapui:display_scenarios')
    
    if request.method == 'POST':
        form = ScenarioForm(request.POST, instance=scenario)
        if form.is_valid():
            form.save()
            messages.success(request, f'Successfully updated scenario "{scenario.title}".')
            return redirect('powermapui:display_scenarios')
    else:
        form = ScenarioForm(instance=scenario)
    
    context = {
        'form': form,
        'scenario': scenario,
        'demand_year': request.session.get('demand_year'),
        'config_file': request.session.get('config_file'),
    }
    return render(request, 'edit_scenario.html', context)

def delete_scenario(request, scenario_id):
    """
    View to delete an existing scenario and its facility associations.
    """
    scenario = get_object_or_404(Scenarios, pk=scenario_id)
    
    # Protect 'Current' scenario from deletion
    if scenario.title == 'Current':
        messages.error(request, 'The "Current" scenario cannot be deleted.')
        return redirect('powermapui:display_scenarios')
    
    if request.method == 'POST':
        scenario_title = scenario.title
        
        # Delete the scenario (MariaDB CASCADE will handle ScenariosFacilities)
        scenario.delete()
        
        messages.success(request, f'Successfully deleted scenario "{scenario_title}" and all its facility associations.')
        return redirect('powermapui:display_scenarios')
    
    # For GET requests, show confirmation page
    facility_count = ScenariosFacilities.objects.filter(idscenarios=scenario).count()
    
    context = {
        'scenario': scenario,
        'facility_count': facility_count,
        'demand_year': request.session.get('demand_year'),
        'config_file': request.session.get('config_file'),
    }
    return render(request, 'delete_scenario_confirm.html', context)

@require_http_methods(["POST"])
def delete_scenario_ajax(request, scenario_id):
    """
    AJAX view to delete a scenario without page reload.
    """
    try:
        scenario = get_object_or_404(Scenarios, pk=scenario_id)
        
        # Protect 'Current' scenario from deletion
        if scenario.title == 'Current':
            return JsonResponse({
                'success': False, 
                'error': 'The "Current" scenario cannot be deleted.'
            })
        
        scenario_title = scenario.title
        facility_count = ScenariosFacilities.objects.filter(idscenarios=scenario).count()
        
        # Delete the scenario (cascade will handle facility associations)
        scenario.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'Successfully deleted scenario "{scenario_title}" and {facility_count} facility associations.'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Error deleting scenario: {str(e)}'
        })

def clone_scenario(request):
    """
    View to clone an existing scenario and its facility associations.
    """
    demand_year = request.session.get('demand_year', '')
    scenario_session = request.session.get('scenario', '')
    config_file = request.session.get('config_file', '')
    
    # Get all scenarios for dropdown selection
    all_scenarios = Scenarios.objects.all()
    
    if request.method == 'POST':
        # Process form submission
        source_scenario_id = request.POST.get('source_scenario')
        new_title = request.POST.get('title')
        new_description = request.POST.get('description', '')
        
        # Form validation
        if not source_scenario_id or not new_title:
            messages.error(request, 'Please select a source scenario and provide a name for the new scenario.')
            return redirect('powermapui:clone_scenario')
        
        # Check if scenario name already exists
        if Scenarios.objects.filter(title=new_title).exists():
            messages.error(request, f'A scenario with the name "{new_title}" already exists. Please choose a different name.')
            return redirect('powermapui:clone_scenario')
        
        try:
            # Get the source scenario
            source_scenario = Scenarios.objects.get(pk=source_scenario_id)
            
            # Create new scenario
            new_scenario = Scenarios.objects.create(
                title=new_title,
                description=new_description
            )
            
            # Clone all facility associations (one by one to trigger signals)
            source_associations = ScenariosFacilities.objects.filter(idscenarios=source_scenario)
            association_count = 0
            
            for assoc in source_associations:
                ScenariosFacilities.objects.create(
                    idscenarios=new_scenario,
                    idfacilities=assoc.idfacilities
                )  # This triggers signals
                association_count += 1
            
            messages.success(
                request, 
                f'Successfully created new scenario "{new_title}" based on "{source_scenario.title}" with {association_count} facilities.'
            )
            
            # Redirect to the scenario management page
            return HttpResponseRedirect(reverse('powermapui:display_scenarios'))
            
        except Exception as e:
            messages.error(request, f'Error creating scenario: {str(e)}')
            return redirect('powermapui:clone_scenario')
    
    # Display the form for GET requests
    context = {
        'all_scenarios': all_scenarios,
        'demand_year': demand_year,
        'scenario': scenario_session,
        'config_file': config_file,
    }
    
    return render(request, 'clone_scenario.html', context)
