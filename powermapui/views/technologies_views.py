# technologies/views.py
from siren_web.forms import DemandYearForm
from sqlalchemy.sql import text
from siren_web.database_operations import fetch_full_generator_storage_data
from django.db.models import Prefetch
from django.shortcuts import render, redirect
from django.conf import settings
from siren_web.models import Technologies, Storageattributes, Generatorattributes

def technologies(request):
    # Default demand year
    weather_year = request.session.get('weather_year', 2024)
    demand_year = request.session.get('demand_year', 2024)
    scenario = request.session.get('scenario')
    config_file = request.session.get('config_file')
    success_message = ""
    technology_name = request.GET.get('technology_name', '')
    
    # Handle form submission
    if request.method == 'POST':
        demand_year_form = DemandYearForm(request.POST)
        if demand_year_form.is_valid():
            demand_year = demand_year_form.cleaned_data['demand_year']
            # Save to session
            request.session['demand_year'] = demand_year
    else:
        # Handle GET request with demand_year parameter
        url_demand_year = request.GET.get('demand_year')
        if url_demand_year:
            try:
                demand_year = int(url_demand_year)
                request.session['demand_year'] = demand_year
            except ValueError:
                pass
    
    # Get the queryset of Technologies with the selected demand year
    technology_queryset = fetch_full_generator_storage_data(demand_year)
    
    # Attribute explanations
    attribute_explain = {
        'area': 'The area occupied by a technology.',
        'capacity': 'The capacity of the technology in mW (generation) or MWhs (storage).',
        'capacity_max':'The maximum capacity of the technology in mW (generation) or MWhs (storage).',
        'capacity_min':'The minimum capacity of the technology in mW (generation) or MWhs (storage).',
        'function':'The role it plays in the grid.',
        'capex':'The initial capital expenditure for the technology.',
        'discharge_loss':'The percentage capacity that is lost in discharging.',
        'discharge_max':'The maxiumum percentage of storage capacity that can be discharged.',
        'discount_rate':'The discount rate applied to the technology.',
        'dispatchable':'The technology can be dispatched at any time when required.',
        'emissions':'CO2 emmissions in kg/mWh',
        'fuel': 'The cost of fuel consumed by the technology.',
        'fom':'The fixed operating cost of the technology.',
        'lifetime':'The operational lifetime of the technology.',
        'parasitic_loss':'The percentage of storage capacity lost other than by charging or discharging.',
        'rampdown_max':'The maximum rampdown rate of the technology.',
        'rampup_max':'The maximum rampup rate of the technology.',
        'recharge_loss':'The percentage capacity that is lost in recharging.',
        'recharge_max':'The maximum recharge rate of the technology.',
        'renewable':'Whether the technology can be renewed.',
        'vom':'The variable operating cost of the technology.',
        'year':'The year of reference.',
    }
    
    # Initialize form with current demand_year
    demand_year_form = DemandYearForm(initial={'demand_year': demand_year})
    
    context = {
        'demand_year_form': demand_year_form,
        'technology_queryset': technology_queryset,
        'attribute_explain': attribute_explain,
        'weather_year': weather_year,
        'demand_year': demand_year, 
        'scenario': scenario, 
        'config_file': config_file,
        'success_message': success_message
    }
    
    return render(request, 'technologies.html', context)
