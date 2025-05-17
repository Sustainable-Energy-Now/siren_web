# forms.py
from django import forms
from siren_web.models import Scenarios, TechnologyYears
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Div, Field, Submit
from crispy_forms.bootstrap import FormActions

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

class DemandYearForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super(DemandYearForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.form_action = '/technologies/'
        self.layout = Layout(
            Div(
                Field('demand_year', css_class='row col-md-4'),
                css_class='row'
            ),
            FormActions(
                Submit('refresh', 'Refresh', css_class='btn btn-primary')
            )
        )
        
        year_choices = [(year, year) for year in TechnologyYears.objects.values_list('year', flat=True).distinct()]
        self.fields['demand_year'] = forms.ChoiceField(
            choices=year_choices,
            required=True
        )