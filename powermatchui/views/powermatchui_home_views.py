from django.views.generic import TemplateView

class PowerPlotHomeView(TemplateView):
    template_name = 'powermatchui_home'


# homes_views.py
from decimal import Decimal
from django.apps import apps
from django.contrib.auth.decorators import login_required
from django.db.models import Max
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.urls import path
from ..forms import DemandYearScenario
from siren_web.models import Demand

@login_required
def powermatchui_home(request):
    demand_year = request.session.get('demand_year', '')  # Get demand_year and scenario from session or default to empty string
    scenario= request.session.get('scenario', '')
    success_message = ""
    if request.method == 'POST':
        # Handle form submission
        demand_year_scenario = DemandYearScenario(request.POST)
        if demand_year_scenario.is_valid():
            demand_year = demand_year_scenario.cleaned_data['demand_year']
            request.session['demand_year'] = demand_year
            scenario = demand_year_scenario.cleaned_data['scenario']
            request.session['scenario'] = scenario # Assuming scenario is an instance of Scenarios
            success_message = "Settings updated."
    demand_year_scenario = DemandYearScenario()

    context = {
        'demand_year_scenario': demand_year_scenario,
        'success_message': success_message, 'demand_year': demand_year, 'scenario': scenario
        }
    return render(request, 'powermatchui_home.html', context)