# forms.py
from django import forms
from .models import Scenarios, Technologies

class HomeForm(forms.Form):
    load_year = forms.ChoiceField(
        choices=[('2021', '2021'), ('2022', '2022')],
        initial='2022',
        widget=forms.Select(attrs={'class': 'form_input'})
        )

    scenario = forms.ModelChoiceField(
        queryset=Scenarios.objects.all().values_list('title', flat=True),
        empty_label=None,
        label='Select a Scenario',  # Add a label for the dropdown
        to_field_name='title',  # Use 'title' as the value for the selected choice
        widget=forms.Select(attrs={'class': 'form_input'})
    )

    LEVEL_OF_DETAIL_CHOICES = [
    ('Summary', 'Summary'),
    ('Detailed', 'Detailed'),
    ]
    
    level_of_detail = forms.ChoiceField(choices=LEVEL_OF_DETAIL_CHOICES, initial='Summary', widget=forms.RadioSelect)


class RunBatchForm(forms.Form):
    LEVEL_OF_DETAIL_CHOICES = [
    ('Summary', 'Summary'),
    ('Detailed', 'Detailed'),
    ]
    
    level_of_detail = forms.ChoiceField(choices=LEVEL_OF_DETAIL_CHOICES, initial='Summary', widget=forms.RadioSelect)

class RunOptimisationForm(forms.Form):
    LEVEL_OF_DETAIL_CHOICES = [
    ('Summary', 'Summary'),
    ('Detailed', 'Detailed'),
    ]
    
    level_of_detail = forms.ChoiceField(choices=LEVEL_OF_DETAIL_CHOICES, initial='Summary', widget=forms.RadioSelect)

class MeritOrderForm(forms.Form):
    merit_order = forms.ModelMultipleChoiceField(queryset=Technologies.objects.none(), widget=forms.SelectMultiple(attrs={'class': 'sortable'}))
    excluded_resources = forms.ModelMultipleChoiceField(queryset=Technologies.objects.none(), widget=forms.SelectMultiple(attrs={'class': 'sortable'}))
