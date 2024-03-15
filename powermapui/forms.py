# forms.py
from django import forms
from siren_web.models import Scenarios, Technologies, variations
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Div, Field

class ScenarioForm(forms.ModelForm):
    class Meta:
        model = Scenarios
        fields = ['title', 'description']
        labels = {
            'title': 'Scenario Title',
            'description': 'Scenario Description',
        }
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control'}),
        }
        
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