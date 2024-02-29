from django.db.models import Model
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.http import HttpResponse, JsonResponse
from ..models import Analysis, Demand, facilities, Generatorattributes, Genetics, Optimisation, Scenarios, Settings, Storageattributes, Technologies, Zones

def siren_system_view(request):
    load_year = request.session.get('load_year')
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
            'Technologies': Technologies,
            'Zones': Zones,
        }

        # Get the model class based on the table name
        model_class = models.get(table)

        if model_class and issubclass(model_class, Model):  # Check if it's a valid model class
            # Get a sample of the model
            sample_data = [list(row) for row in model_class.objects.all()[:5].values_list()]
            # sample_data = [['A','B','C','D'],['D','E','F','G'],['G','H','I','J'],['J','K','L','M'],['M','N','O','P']]
            # # column_names = [field.name for field in model_class._meta.get_fields()]
            column_names = [field.name for field in model_class._meta.fields]
            
            # Construct a list of dictionaries from the sample rows
            # sample_data = []
            # for row in sample_rows:
            #     data_row = {}
            #     for column_name in column_names:
            #         data_row[column_name] = getattr(row, column_name)
            #     sample_data.append(data_row)
            # Add model information and sample rows to the context
            context['model_name'] = table
            context['model_description'] = model_class._meta.verbose_name_plural.capitalize()  # Assuming models have a verbose_name_plural set
            context['sample_data'] = sample_data
            # column_names = [field.verbose_name.capitalize() for field in model_class._meta.fields]
            # Get the column names of the model

            context['column_names'] = column_names
            context['load_year'] = load_year
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
