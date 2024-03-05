# forms.py
from django import forms
from .models import Scenarios, Technologies

class HomeForm(forms.Form):
    demand_year = forms.ChoiceField(
        choices=[('2022', '2022'), ('2023', '2023')],
        label='Select a Demand Year',
        initial='2023',
        widget=forms.Select(attrs={'class': 'form_input'})
        )

    scenario = forms.ModelChoiceField(
        queryset=Scenarios.objects.all().values_list('title', flat=True),
        empty_label=None,
        label='Select a Scenario',  # Add a label for the dropdown
        to_field_name='title',  # Use 'title' as the value for the selected choice
        widget=forms.Select(attrs={'class': 'form_input'})
    )

class RunPowermatchForm(forms.Form):
    LEVEL_OF_DETAIL_CHOICES = [
    ('Summary', 'Summary'),
    ('Detailed', 'Detailed'),
    ]
    
    level_of_detail = forms.ChoiceField(
        choices=LEVEL_OF_DETAIL_CHOICES,
        initial='Summary',
        widget=forms.RadioSelect,
        required=False  # Make the field optional
        )
    
class RunBatchForm(forms.Form):
    iterations = forms.IntegerField(min_value=1, initial=1)
    # Define fields for each technology
    def __init__(self, *args, **kwargs):
        technologies = kwargs.pop('technologies')
        super(RunBatchForm, self).__init__(*args, **kwargs)
        for technology, values in technologies.items():
            self.fields[f'capacity_{technology}'] = forms.IntegerField(initial=values[1], required=False)
            self.fields[f'multiplier_{technology}'] = forms.FloatField(initial=values[2], required=False)
            self.fields[f'step_{technology}'] = forms.FloatField(required=False)
        
    def clean(self):
        cleaned_data = super().clean()
        # Check if at least one 'step' field has a value
        steps = [value for key, value in cleaned_data.items() if key.startswith('step_') and value is not None]
        if not steps:
            raise forms.ValidationError("At least one step value is required")
        return cleaned_data


class RunOptimisationForm(forms.Form):
    LEVEL_OF_DETAIL_CHOICES = [
    ('Summary', 'Summary'),
    ('Detailed', 'Detailed'),
    ]
    
    level_of_detail = forms.ChoiceField(choices=LEVEL_OF_DETAIL_CHOICES, initial='Summary', widget=forms.RadioSelect)

class MeritOrderForm(forms.Form):
    merit_order = forms.ModelMultipleChoiceField(queryset=Technologies.objects.none(), widget=forms.SelectMultiple(attrs={'class': 'sortable'}))
    excluded_resources = forms.ModelMultipleChoiceField(queryset=Technologies.objects.none(), widget=forms.SelectMultiple(attrs={'class': 'sortable'}))
