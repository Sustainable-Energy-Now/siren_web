from django.shortcuts import render, redirect, get_object_or_404
from django.forms import modelformset_factory
from ..forms import ScenarioForm
from ..models import Scenarios, facilities, ScenariosFacilities

def create_scenario(request):
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
            return render(request, 'create_scenario.html', context)

    else:
        formset = facility_formset(queryset=ScenariosFacilities.objects.none())

    context = {
        'scenario_form': scenario_form,
        'facility_formset': formset,
    }
    return render(request, 'create_scenario.html', context)