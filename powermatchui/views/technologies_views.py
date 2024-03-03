from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.apps import apps
from django.http import HttpResponse

# technologies_views.py
@login_required
def display_technologies(request):
    demand_year = request.session.get('demand_year')
    scenario = request.session.get('scenario')
    return render(request, 'under_construction.html')