from ..database_operations import fetch_technologies_data
from django.shortcuts import render
from django.http import HttpResponse
from ..models import Scenarios  # Import the Scenario model
from ..forms import BatchForm

def home(request):
    scenarios = Scenarios.objects.all()  # Retrieve all scenarios from the database
    return render(request, 'home.html', {'scenarios': scenarios})

def clear_scenario(request, scenario_id):
    # Logic to clear scenario with the given ID from the database
    return HttpResponse("Scenario has been cleared.")  # Return a response indicating success

def run_batch(request):
    if request.method == 'POST':
        # Handle form submission
        form = BatchForm(request.POST)
        if form.is_valid():
            # Process form data
            selected_scenario = form.cleaned_data['scenario']
            # Perform further actions with the selected scenario
    else:
        # Render the form
        load_year = 2022
        technologies = fetch_technologies_data(request, load_year)
        form = BatchForm()
        context = {'form': form, 'technologies': technologies}
    return render(request, 'run_batch.html', context)