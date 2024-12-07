from django.shortcuts import render, redirect, get_object_or_404
from django.forms import modelformset_factory
from django.urls import reverse
from ..forms import ScenarioForm
from siren_web.models import Scenarios, facilities, ScenariosFacilities

def create_scenario(request):
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
