# forms.py
from django import forms
from .models import Scenarios, Technologies

class RunBatchForm(forms.Form):
    load_year = forms.ChoiceField(choices=[('2021', '2021'), ('2022', '2022')], initial='2022')

    scenario = forms.ModelChoiceField(
        queryset=Scenarios.objects.all(),
        empty_label=None,
        label='Select a Scenario',  # Add a label for the dropdown
        to_field_name='idscenarios'  # Use 'id' as the value for the selected choice
    )
    
    LEVEL_OF_DETAIL_CHOICES = [
    ('Summary', 'Summary'),
    ('Detailed', 'Detailed'),
    ]
    
    level_of_detail = forms.ChoiceField(choices=LEVEL_OF_DETAIL_CHOICES, initial='Summary', widget=forms.RadioSelect)

class MeritOrderForm(forms.Form):
    merit_order = forms.ModelMultipleChoiceField(queryset=Technologies.objects.none(), widget=forms.SelectMultiple(attrs={'class': 'sortable'}))
    excluded_resources = forms.ModelMultipleChoiceField(queryset=Technologies.objects.none(), widget=forms.SelectMultiple(attrs={'class': 'sortable'}))
