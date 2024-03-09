from django.shortcuts import render
from ..models import Technologies

def display_technologies(request):
    demand_year = request.session.get('demand_year', '')  # Get demand_year and scenario from session or default to empty string
    scenario= request.session.get('scenario', '')
    success_message = ""
    technologies = Technologies.objects.all()
    fields = [
        'idtechnologies', 'technology_name', 'year', 'image', 'caption', 'category', 'renewable',
        'dispatchable', 'merit_order', 'capex', 'fom', 'vom', 'lifetime', 'discount_rate',
        'description', 'capacity', 'mult', 'capacity_max', 'capacity_min', 'emissions', 'initial',
        'lcoe', 'lcoe_cf'
        ]
    context = {
        'technologies': technologies,
        'fields': fields,
        'success_message': success_message, 'demand_year': demand_year, 'scenario': scenario
    }
    return render(request, 'technologies_list.html', context)