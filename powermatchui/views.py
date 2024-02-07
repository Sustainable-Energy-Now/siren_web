from django.shortcuts import render
from .models import Analysis, constraints, Demand, Scenarios, Settings

# Create your views here.
# views.py
from django.shortcuts import render
from django.http import HttpResponse
from .forms import LoadYearForm

def main(request):
    if request.method == 'POST':
        form = LoadYearForm(request.POST)
        if form.is_valid():
            load_year = form.cleaned_data['load_year']
            # Perform necessary actions with the selected load year
            return HttpResponse("Submission successful!")
    else:
        form = LoadYearForm()
    my_view()
    return render(request, 'main.html', {'form': form})

# urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.main, name='main'),
]

# forms.py
from django import forms

class LoadYearForm(forms.Form):
    load_year = forms.ChoiceField(choices=[('2021', '2021'), ('2022', '2022')], initial='2022')

from .database_operations import fetch_settings_data

def my_view():
    settings = fetch_settings_data()
    # Use settings data as needed
