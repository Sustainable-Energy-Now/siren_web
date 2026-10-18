from django.conf import settings
from django.contrib.auth import authenticate, login
from django.db.models import Model
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.http import JsonResponse
from siren_web.models import Analysis, facilities, Generatorattributes, \
    sirensystem, Scenarios, Settings, Storageattributes, SupplyFactorMatrix, Technologies, Zones
import markdown
import os
from django.conf import settings

def get_description(name, sirensystem_model):
    try:
        # Use get_object_or_404 for efficient retrieval and handling of non-existent objects
        sirensystem = get_object_or_404(sirensystem_model, name=name)
        description = sirensystem.description
    except sirensystem.DoesNotExist:
        # Handle the case where the object with the given name doesn't exist
        description = "No description available."  # Or set a custom error message
    return description

# Website membership status -> (shared Siren Web account, USER_PASS key)
MEMBERSHIP_ACCOUNTS = {
    'Active': ('member', 'member_pass'),          # full access
    'Lapsed': ('lapsed', 'lapsed_pass'),          # limited access
    'Non member': ('subscriber', 'subscriber_pass'),  # no access
}

def login_from_membership_params(request):
    """Log in the shared account matching the website's ?membership_status=
    parameter (the website embeds it in links to Siren Web). Does nothing if
    the user is already logged in or the status is missing/unknown."""
    if request.user.is_authenticated:
        return
    account = MEMBERSHIP_ACCOUNTS.get(request.GET.get('membership_status', ''))
    if not account:
        return
    user_name, pass_key = account
    user = authenticate(request, username=user_name, password=settings.USER_PASS[pass_key])
    if user is not None:
        login(request, user)

def home_view(request):
    success_message = ""
    member_name = request.GET.get('member_name', '')
    email_address = request.GET.get('email_address', '')
    login_from_membership_params(request)
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
    context['success_message'] = success_message
    if table:
        # Dictionary mapping table names to their respective model classes
        models = {
            'Analysis': Analysis,
            'Facilities': facilities,
            'Generatorattributes': Generatorattributes,
            'Scenarios': Scenarios,
            'Settings': Settings,
            'Storageattributes': Storageattributes,
            'SupplyFactors': SupplyFactorMatrix,
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

def release_notes(request):
    notes_file = os.path.join(settings.BASE_DIR, 'release_notes.md')
    try:
        with open(notes_file, 'r', encoding='utf-8') as f:
            content = f.read()
        html_content = markdown.markdown(content)
    except FileNotFoundError:
        html_content = "<p>Release notes not found.</p>"
    
    return render(request, 'release_notes.html', {'content': html_content})