from django.conf import settings
from django.contrib.auth import authenticate, login
from django.db.models import Model
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.http import HttpResponse, JsonResponse
from siren_web.models import Analysis, Demand, facilities, Generatorattributes, \
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

def home_view(request):
    demand_year = request.session.get('demand_year')
    scenario = request.session.get('scenario')
    success_message = ""
    member_name = request.GET.get('member_name', '')
    email_address = request.GET.get('email_address', '')
    membership_status = request.GET.get('membership_status', '')

    user = authenticate(request, username='webmaster', password='SenMdl!0')
    # if user is not None:
    #     login(request, user)
    #     # Redirect to a success page
    # else:
        # Handle authentication failure
    # Handle the membership status and grant access accordingly
    # if (membership_status):
    #     if membership_status == 'active':
    #         # Grant full access
    #         access_level = 'full'
    #     elif membership_status == 'lapsed':
    #         # Grant limited access
    #         access_level = 'limited'
    #     else:
    #         # Grant no access (non-member)
    #         access_level = 'none'
    #     context = {
    #         'member_name': member_name,
    #         'email_address': email_address,
    #         'membership_status': membership_status,
    #         'access_level': access_level,
    #     }
    # if not request.user.is_authenticated:
    # user = authenticate(request, username=user_name, password=password)
        
    context = {
        'home_view_url': reverse('home')
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
            # return render(request, 'home.html', context)
        else:
            # Return a JSON response indicating that no action should be taken
            return JsonResponse(context)
    else:
        # Render the main template if no model is specified or if the model is not found
        return render(request, 'home.html', context)

    # Define a custom template tag function
