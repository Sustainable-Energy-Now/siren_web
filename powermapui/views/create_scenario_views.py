from django.contrib import messages
from django.shortcuts import render, redirect
from django.forms import modelformset_factory
from django.http import HttpResponseRedirect
from django.urls import reverse
from ..forms import ScenarioForm
from siren_web.models import Scenarios, facilities, ScenariosFacilities

def display_scenario(request):
    demand_year = request.session.get('demand_year')
    scenario = request.session.get('scenario')
    config_file = request.session.get('config_file')
    success_message = ""
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
                sf.save()
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
        'success_message': success_message
    }
    return render(request, 'create_scenario.html', context)

def update_scenario(request):
    demand_year = request.session.get('demand_year')
    scenario = request.session.get('scenario')
    config_file = request.session.get('config_file')
    success_message = ""
    all_scenarios = Scenarios.objects.all()
    all_facilities = facilities.objects.all()
    scenario_form = ScenarioForm(request.POST or None)
    facility_formset = modelformset_factory(ScenariosFacilities, fields=('idfacilities',), extra=0)


    if request.method == 'POST':
        for scenario in all_scenarios:
            facility_ids = request.POST.getlist(f'scenario_{scenario.pk}_facilities')
            scenario_facilities = ScenariosFacilities.objects.filter(idscenarios=scenario)
            
            # Remove facilities that are not in the submitted list
            scenario_facilities.exclude(idfacilities__in=facility_ids).delete()

            # Add facilities that are in the submitted list but not in the database
            new_facility_ids = set(facility_ids) - set(scenario_facilities.values_list('idfacilities', flat=True))
            new_scenario_facilities = [ScenariosFacilities(idscenarios=scenario, idfacilities_id=facility_id) for facility_id in new_facility_ids]
            ScenariosFacilities.objects.bulk_create(new_scenario_facilities)
            
    checkbox_status = {}
    for facility in all_facilities:
        checkbox_status[facility.idfacilities] = {}
        for scenario in all_scenarios:
            checkbox_status[facility.idfacilities][scenario.idscenarios] = ScenariosFacilities.objects.filter(idfacilities=facility, idscenarios=scenario).exists()
            
    context = {
        'scenario_form': scenario_form,
        'facility_formset': facility_formset,
        'all_scenarios': all_scenarios,
        'all_facilities': all_facilities,
        'checkbox_status': checkbox_status,
        'demand_year': demand_year,
        'scenario': scenario,
        'config_file': config_file,
        'success_message': success_message
    }
    return render(request, 'create_scenario.html', context)

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
            return redirect('clone_scenario')
        
        try:
            # Get the source scenario
            source_scenario = Scenarios.objects.get(pk=source_scenario_id)
            
            # Create new scenario
            new_scenario = Scenarios.objects.create(
                title=new_title,
                description=new_description
            )
            
            # Clone all facility associations
            source_associations = ScenariosFacilities.objects.filter(idscenarios=source_scenario)
            
            # Get a count of the actual associations that will be cloned
            association_count = source_associations.count()
            
            # Create list for bulk creation
            new_associations = []
            
            for assoc in source_associations:
                new_associations.append(
                    ScenariosFacilities(
                        idscenarios=new_scenario,
                        idfacilities=assoc.idfacilities
                    )
                )
            
            # Bulk create all associations at once for efficiency
            if new_associations:
                ScenariosFacilities.objects.bulk_create(new_associations)
            
            messages.success(
                request, 
                f'Successfully created new scenario "{new_title}" based on "{source_scenario.title}" with {association_count} facilities.'
            )
            
            # Redirect to the scenario management page
            return HttpResponseRedirect(reverse('display_scenarios'))
            
        except Exception as e:
            messages.error(request, f'Error creating scenario: {str(e)}')
            return redirect('clone_scenario')
    
    # Display the form for GET requests
    context = {
        'all_scenarios': all_scenarios,
        'demand_year': demand_year,
        'scenario': scenario_session,
        'config_file': config_file,
    }
    
    return render(request, 'clone_scenario.html', context)
