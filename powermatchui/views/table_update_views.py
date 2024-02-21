from decimal import Decimal
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

def select_table(request):
    table_names = get_table_names()
    return render(request, 'table_update_page.html', {'table_names': table_names})

def update_table(request):
    load_year = request.session.get('load_year')
    scenario = request.session.get('scenario')
    if request.method == 'POST':
        action = request.POST.get('action')  # Get the value of the "action" field
        if action == 'populate':
            # Code to handle selecting the table and populating the page
            # This code will be executed when the "Submit" button is clicked
            selected_table_name = request.POST.get('table_selection')
            selected_model = apps.get_model('powermatchui', selected_table_name)
            primary_key_name = selected_model._meta.pk.name
            # Fetch column names dynamically
            column_names = [field.name for field in selected_model._meta.fields]
            # Fetch rows for all column names
            #table_entries = selected_model.objects.values(*[field.name for field in selected_model._meta.fields if not field.is_relation])
            #table_rows = selected_model.objects.values()
            table_entries = selected_model.objects.all()
            return render(request, 'table_update_page.html', {'selected_table_name': selected_table_name, 'primary_key_name': primary_key_name, 'column_names': column_names, 'table_entries': table_entries})
        elif action == 'save':
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
                    if field_type != 'ForeignKey':
                        if field_type == 'DecimalField':
                            new_value = Decimal(new_value)
                        elif field_type == 'IntegerField':
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
            return render(request, 'table_update_page.html', \
                {'column_names': column_names, 'table_entries': table_entries, 'success_message': 'Table has been updated.', 'load_year': load_year, 'scenario': scenario})

    # If the request method is not POST or action is not specified, render the initial page
    # This may include rendering the table initially without any changes
    return render(request, 'table_update_page.html')