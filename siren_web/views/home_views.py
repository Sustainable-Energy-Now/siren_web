from django.conf import settings
from django.contrib.auth import authenticate, login
from django.db.models import Model
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.http import HttpResponse, JsonResponse
from siren_web.models import Analysis, Demand, facilities, Generatorattributes, \
    Genetics, Optimisations, sirensystem, Scenarios, Settings, Storageattributes, supplyfactors, Technologies, Zones


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
    try:
        scenario_obj: Scenarios = Scenarios.objects.get(title=scenario)
    except Scenarios.DoesNotExist: # Handle the case where the scenario title no longer exists
        scenario = None
        request.session['scenario'] = scenario
        demand_year =None
        request.session['demand_year'] = demand_year
    config_file = request.session.get('config_file')
    success_message = ""
    member_name = request.GET.get('member_name', '')
    email_address = request.GET.get('email_address', '')
    membership_status = request.GET.get('membership_status', '')
    if not request.user.is_authenticated:
        if (membership_status):
            if membership_status == 'Active':
                # Grant full access
                user_name = 'member'
                user_password = settings.USER_PASS['member_pass']
            elif membership_status == 'Lapsed':
                # Grant limited access
                user_name = 'lapsed'
                user_password = settings.USER_PASS['lapsed_pass']
            elif membership_status == 'Non member':
                # Grant no access (non-member)
                user_name = 'subscriber'
                user_password = settings.USER_PASS['subscriber_pass']
            else:
            # Handle authentication failure
                pass
            try:
                if user_name is not None:
                    # Authenticate the user
                    user = authenticate(request, username=user_name, password=user_password)
            except UnboundLocalError:
                # Handle the case where user_name isn't defined
                user = None
            if user is not None:
                login(request, user)
    # Handle the membership status and grant access accordingly
    #     context = {
    #         'member_name': member_name,
    #         'email_address': email_address,
    #         'membership_status': membership_status,
    #         'access_level': access_level,
    #     }
    # user = authenticate(request, username=user_name, password=password)
        
    context = {
        'home_view_url': reverse('home')
    }

    # Handle the request
    table = request.GET.get('table')  # Get the title parameter from the request

    # Perform actions based on the table
    context['demand_year'] = demand_year
    context['scenario'] = scenario
    context['config_file'] = config_file
    context['success_message'] = success_message
    if table:
        # Dictionary mapping table names to their respective model classes
        models = {
            'Analysis': Analysis,
            'Demand': Demand,
            'Facilities': facilities,
            'Generatorattributes': Generatorattributes,
            'Genetics': Genetics,
            'Optimisations': Optimisations,
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
            context['model_description'] = str(get_description(table, sirensystem))
            context['sample_data'] = sample_data
            context['column_names'] = column_names
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