from django.shortcuts import render, redirect
from django.apps import apps
from django.http import HttpResponse
from .forms import LoadYearForm

def main(request):
    if request.method == 'POST':
        form = LoadYearForm(request.POST)
        if form.is_valid():
            load_year = form.cleaned_data['load_year']
            # Perform necessary actions with the selected load year
            return HttpResponse("Submission successful!")
    else:
        form = LoadYearForm()
    my_view()
    return render(request, 'main.html', {'form': form})

# views.py
def get_table_names():
    table_names = []
    for model in apps.get_models():
        table_names.append(model._meta.db_table)
    return table_names

def select_table(request):
    table_names = get_table_names()
    return render(request, 'table_update_page.html', {'table_names': table_names})

def table_update_page(request):
    if request.method == 'POST':
        selected_table_name = request.POST.get('table_selection')
        selected_model = apps.get_model('powermatchui', selected_table_name)
        # Fetch column names dynamically
        column_names = [field.name for field in selected_model._meta.fields]
        # Fetch rows for all column names
        #table_entries = selected_model.objects.values(*[field.name for field in selected_model._meta.fields if not field.is_relation])
        #table_rows = selected_model.objects.values()
        table_entries = selected_model.objects.all()
        return render(request, 'table_update_page.html', {'column_names': column_names, 'table_entries': table_entries})
    else:
        # If the request method is not POST, render the template without table entries
        return render(request, 'table_update_page.html')

from django.urls import path
from . import views

urlpatterns = [
    path('', views.main, name='main'),
]

# forms.py
from django import forms

class LoadYearForm(forms.Form):
    load_year = forms.ChoiceField(choices=[('2021', '2021'), ('2022', '2022')], initial='2022')

from .database_operations import fetch_settings_data

def my_view():
    settings = fetch_settings_data()
    # Use settings data as needed


from .models import YourModel  # Import your model

def table_update_process(request):
    if request.method == 'POST':
        column_names = request.POST.getlist('column_name')  # Assuming 'column_name' is the name attribute of the input fields
        table_entries = YourModel.objects.all()  # Fetch all objects from the database

        # Iterate over the submitted form data
        for entry in table_entries:
            for column_name in column_names:
                # Get the value of the input field
                new_value = request.POST.get(f'{column_name}_{entry.id}')  # Assuming each input field has a unique identifier based on entry id
                # Update the corresponding object in the database
                setattr(entry, column_name, new_value)  # Set the new value for the attribute/column
                entry.save()  # Save the changes to the database

        # Optionally, you may redirect the user to another page after the update
        return redirect('some-view-name')

    # If the request method is not POST, redirect the user back to the original page
    return redirect('table_update_page')
