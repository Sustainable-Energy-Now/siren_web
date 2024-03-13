# technologies/views.py
import pandas as pd
from sqlalchemy.sql import text
from siren_web.database_operations import fetch_full_generator_storage_data
from django.db.models import Prefetch
from django.shortcuts import render
from django.conf import settings
from siren_web.models import Technologies, Storageattributes, Generatorattributes

def technologies_detail(request):
    demand_year = request.session.get('demand_year')
    scenario = request.session.get('scenario')
    success_message = ""
    technology_name = request.GET.get('technology_name', '')
    # Get the queryset of Technologies with related StorageAttributes and GeneratorAttributes
    technology_queryset = Technologies.objects.prefetch_related(
        Prefetch('storageattributes_set', queryset=Storageattributes.objects.filter(idtechnologies__year=demand_year)),
        Prefetch('generatorattributes_set', queryset=Generatorattributes.objects.filter(idtechnologies__year=demand_year))
    )
    attribute_explain = {
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
        'fuel': 'The type of fuel consumed by the technology.',
        'fom':'The fixed operating cost of the technology.',
        'initial': 'The initial value.',
        'lcoe':'The levelised cost of energy.',
        'lcoe_cf':'The levelised cost of energy capacity factor.',
        'lifetime':'The operational lifetime of the technology.',
        'mult':'The capacity multiplier.',
        'merit_order':'The merit order in which the technology is dispatched to meet load.',
        'parasitic_loss':'The percentage of storage capacity lost other than by charging or discharging.',
        'rampdown_max':'The maximum rampdown rate of the technology.',
        'rampup_max':'The maximum rampup rate of the technology.',
        'recharge_loss':'The percentage capacity that is lost in recharging.',
        'recharge_max':'The maximum recharge rate of the technology.',
        'renewable':'Whether the technology can be renewed.',
        'row_num':'sort field.',
        'vom':'The variable operating cost of the technology.',
        'year':'The year of reference.',
        }
    data = []
    for obj in technology_queryset:
        obj_data = {}
        for field in obj._meta.fields:
            value = getattr(obj, field.name)
            obj_data[field.name] = value
        data.append(obj_data)
        explanation = attribute_explain[field.name]
    context = {
        'technology_queryset': technology_queryset,
        'attribute_explain': attribute_explain,
        'demand_year': demand_year, 'scenario': scenario, 'success_message': success_message
    }
    return render(request, 'technologies_detail.html', context)