from siren_web.database_operations import fetch_included_technologies_data, fetch_module_settings_data, \
    fetch_scenario_settings_data
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.http import HttpResponse
from siren_web.models import Scenarios  # Import the Scenario model
from ..forms import OptimisationForm

def home(request):
    scenarios = Scenarios.objects.all()  # Retrieve all scenarios from the database
    return render(request, 'home.html', {'scenarios': scenarios})

def clear_scenario(request, scenario_id):
    # Logic to clear scenario with the given ID from the database
    return HttpResponse("Scenario has been cleared.")  # Return a response indicating success

# Process form data
@login_required
def run_optimisation(request):
    demand_year = request.session.get('demand_year')
    scenario = request.session.get('scenario')
    success_message = ""
    technologies = {}
    scenario_settings = {}
    if not demand_year:
        success_message = "Set the demand year and scenario in the home page first."
    else:
        scenario_settings = fetch_module_settings_data('Powermatch')
        if not scenario_settings:
            scenario_settings = fetch_scenario_settings_data(scenario)
        technologies = fetch_included_technologies_data(scenario)
        optimisationform = OptimisationForm(technologies=technologies, scenario_settings=scenario_settings)

    if request.method == 'POST':
        # Handle form submission
        form = OptimisationForm(request.POST)
        if form.is_valid():
            # Process form data
            merit_order = request.POST.getlist('merit_order[]')
            # Perform further actions with the selected scenario
                    # Update the merit_order attribute for technologies in the 'Merit Order' column
        for index, tech_id in enumerate(merit_order, start=1):
            technology = Technologies.objects.get(idtechnologies=tech_id)
            technology.merit_order = index
            technology.save()
        success_message = "Optimisation Parameters have been updated."

    context = {'optimisationform': optimisationform, 'technologies': technologies, 'demand_year': demand_year, 'scenario': scenario,'success_message': success_message}
    return render(request, 'optimisation.html', context)
