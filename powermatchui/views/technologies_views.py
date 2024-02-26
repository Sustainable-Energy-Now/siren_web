from decimal import Decimal
from django.shortcuts import render, redirect
from django.apps import apps
from django.http import HttpResponse

# technologies_views.py
def display_technologies(request):
    load_year = request.session.get('load_year')
    scenario = request.session.get('scenario')
    return render(request, 'under_construction.html')