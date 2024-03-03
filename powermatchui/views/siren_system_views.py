from django.db.models import Model
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.http import HttpResponse, JsonResponse
from ..models import Analysis, Demand, facilities, Generatorattributes, \
    Genetics, Optimisation, sirensystem, Scenarios, Settings, Storageattributes, supplyfactors, Technologies, Zones

def get_description(name, sirensystem_model):
    try:
        # Use get_object_or_404 for efficient retrieval and handling of non-existent objects
        sirensystem = get_object_or_404(sirensystem_model, name=name)
        description = sirensystem.description
    except sirensystem.DoesNotExist:
        # Handle the case where the object with the given name doesn't exist
        description = "No description available."  # Or set a custom error message
    return description

def siren_system_view(request):
    demand_year = request.session.get('demand_year')
    scenario = request.session.get('scenario')
    success_message = ""
    context = {
        'siren_system_view_url': reverse('siren_system_view')
    }

    # Handle the request
    table = request.GET.get('table')  # Get the title parameter from the request

    # Perform actions based on the table
    if table:
        # Dictionary mapping table names to their respective model classes
        models = {
            'Analysis': Analysis,
            'Demand': Demand,
            'Facilities': facilities,
            'Generatorattributes': Generatorattributes,
            'Genetics': Genetics,
            'Optimisation': Optimisation,
            'Scenarios': Scenarios,
            'Settings': Settings,
            'Storageattributes': Storageattributes,
            'SupplyFactors': supplyfactors,
            'Technologies': Technologies,
            'Zones': Zones,
        }

        # Get the model class based on the table name
        model_class = models.get(table)

        if model_class and issubclass(model_class, Model):  # Check if it's a valid model class
            # Get a sample of the model
            sample_data = [list(row) for row in model_class.objects.all()[:5].values_list()]

            # Get the column names of the model
            column_names = [field.name for field in model_class._meta.fields]
            context['model_name'] = table
            context['model_description'] = get_description(table, sirensystem)
            context['sample_data'] = sample_data

            context['column_names'] = column_names
            context['demand_year'] = demand_year
            context['scenario'] = scenario
            context['status'] = 'success'

            # Render the modal template with the model information and sample rows
            return JsonResponse(context)
            # return render(request, 'siren_system.html', context)
        else:
            # Return a JSON response indicating that no action should be taken
            return JsonResponse(context)
    else:
        # Render the main template if no model is specified or if the model is not found
        return render(request, 'siren_system.html', context)

    # Define a custom template tag function
