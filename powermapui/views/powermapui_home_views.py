# homes_views.py
from decimal import Decimal
from django.apps import apps
from django.contrib.auth.decorators import login_required
from django.db.models import Max
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from django.urls import path
from siren_web.database_operations import fetch_demand_data, fetch_scenarios_data, fetch_full_generator_storage_data
from siren_web.models import Demand
from powermatchui.powermatch.pmcore import Facility, Optimisation, PM_Facility, powerMatch
from powermatchui.views.exec_powermatch import submit_powermatch

@login_required
def home(request):
    demand_year = request.session.get('demand_year', '')  # Get demand_year and scenario from session or default to empty string
    scenario= request.session.get('scenario', '')
    success_message = ""
    context = {
        'success_message': success_message, 'demand_year': demand_year, 'scenario': scenario
        }
    return render(request, 'powermapui_home.html', context)