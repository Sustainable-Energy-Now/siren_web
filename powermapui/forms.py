# forms.py
from django import forms
from siren_web.models import Scenarios
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