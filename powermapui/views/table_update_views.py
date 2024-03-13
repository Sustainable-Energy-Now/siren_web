from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.apps import apps
from django.http import HttpResponse

# views.py
def get_table_names():
    prefixes_excluded = ['auth_', 'Demand', 'django_']  # List of Tables with prefixes to be excluded
    table_names = [
        model._meta.db_table 
        for model in apps.get_models() 
            if not any(model._meta.db_table.startswith(prefix) for prefix in prefixes_excluded)
    ]
    return table_names

@login_required
def select_table(request):
    demand_year = request.session.get('demand_year', '')  # Get demand_year and scenario from session or default to empty string
    scenario= request.session.get('scenario', '')
    success_message = ""
    table_names = get_table_names()
    selected_table_name = ''
    if request.method == 'POST':
        # Code to handle selecting the table and populating the page
        # This code will be executed when the "Submit" button is clicked
        selected_table_name = request.POST.get('table_selection')
        selected_model = apps.get_model('powermatchui', selected_table_name)
        primary_key_name = selected_model._meta.pk.name
        # Fetch column names dynamically
        column_names = [field.name for field in selected_model._meta.fields]
        # Fetch rows for all column names
        table_entries = selected_model.objects.all()
        context = {
            'success_message': success_message, 'demand_year': demand_year, 'scenario': scenario,
            'table_names': table_names, 'selected_table_name': selected_table_name, 
            'primary_key_name': primary_key_name, 'column_names': column_names, 'table_entries': table_entries,
            'selected_table_name': selected_table_name,
        }
        return render(request, 'table_update_page.html', context)
    else:
        context = {
            'success_message': success_message, 'demand_year': demand_year, 'scenario': scenario,
            'table_names': table_names
        }
        return render(request, 'table_update_page.html', context)

@login_required
def update_table(request):
    demand_year = request.session.get('demand_year')
    scenario = request.session.get('scenario')
    success_message = ""
    if request.method == 'POST':
        action = request.POST.get('action')  # Get the value of the "action" field

        # Code to handle saving changes made to the table
        # This code will be executed when the "Save Changes" button is clicked
        
        # Handle form submission for updating the table
        selected_table_name = request.POST.get('selected_table_name')  # Get the value of the "selected_model" field
        selected_model = apps.get_model('powermatchui', selected_table_name)
        table_entries = selected_model.objects.all() # Fetch all objects from the database
        primary_key_field_name = selected_model._meta.pk.name
        column_names = [field.name for field in selected_model._meta.fields]

        # Iterate over the submitted form data
        for entry in table_entries:
            for column_name in column_names:
                # Get the value of the input f ield
                new_value = request.POST.get(f'{column_name}_{entry.pk}')  # each input field has a unique identifier based on column name and primary key
                current_value = getattr(entry, column_name)
                field_type = entry._meta.get_field(column_name).get_internal_type()
                # Check if the new value is different from the current value
                # Convert new_value to the appropriate data type based on the field type
                if (field_type != 'ForeignKey' and field_type != 'ManyToManyField') and (field_type != 'AutoField'):
                    if field_type == 'DecimalField':
                        new_value = Decimal(new_value)
                    elif field_type == 'IntegerField' or field_type == 'PositiveSmallIntegerField':
                        new_value = int(new_value)
                    elif field_type == 'PositiveIntegerField':
                        new_value = int(new_value)
                    elif field_type == 'FloatField':
                        new_value = float(new_value)
                    if new_value != current_value:
                        # Update the corresponding object in the database
                        setattr(entry, column_name, new_value)  # Set the new value for the attribute/column
                        entry.save()  # Save the changes to the database

         # Render the template with the populated table and success message (if any)
        success_message = f'Successfully updated {selected_table_name} table.'
        table_names = get_table_names()
        context = {
            'column_names': column_names, 'table_entries': table_entries,
            'success_message': success_message, 'demand_year': demand_year, 'scenario': scenario,
            'table_names': table_names, 'selected_table_name' : selected_table_name,
        }
        return render(request, 'table_update_page.html', context)

    # If the request method is not POST or action is not specified, render the initial page
    # This may include rendering the table initially without any changes
    return render(request, 'table_update_page.html')