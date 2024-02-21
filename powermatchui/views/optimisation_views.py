from ..database_operations import fetch_full_generator_storage_data
from django.shortcuts import render
from django.http import HttpResponse
from ..models import Scenarios  # Import the Scenario model
from ..forms import RunOptimisationForm

def home(request):
    scenarios = Scenarios.objects.all()  # Retrieve all scenarios from the database
    return render(request, 'home.html', {'scenarios': scenarios})

def clear_scenario(request, scenario_id):
    # Logic to clear scenario with the given ID from the database
    return HttpResponse("Scenario has been cleared.")  # Return a response indicating success

# Process form data
def run_optimisation(request):
    load_year = request.session.get('load_year')
    scenario = request.session.get('scenario')
    form = RunOptimisationForm(request.POST)
    success_message = ""
    if request.method == 'POST':
        # Handle form submission

        if form.is_valid():
            # Process form data
            merit_order = request.POST.getlist('merit_order[]')
            # Perform further actions with the selected scenario
                    # Update the merit_order attribute for technologies in the 'Merit Order' column
        for index, tech_id in enumerate(merit_order, start=1):
            technology = Technologies.objects.get(idtechnologies=tech_id)
            technology.merit_order = index
            technology.save()
        success_message = "Batch Parameters have been updated."
    else:
        # Render the form
        load_year = 2022
        technologies = fetch_full_generator_storage_data(request, load_year)
        form = RunOptimisationForm()
        
    context = {'form': form, 'technologies': technologies, 'load_year': load_year, 'scenario': scenario,'success_message': success_message}
    return render(request, 'batch.html', context)
