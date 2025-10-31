# forms.py
from django import forms
from django.forms.widgets import DateTimeInput
from siren_web.models import Scenarios, TechnologyYears
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Div, Field, Submit
from crispy_forms.bootstrap import FormActions
from .models import Reference

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

class DemandScenarioSettings(forms.Form):
    weather_year = forms.ChoiceField(
        label='Select a Weather Year',
        initial='2024',
        required=True,
        widget=forms.Select(attrs={'class': 'form_input'})
    )
    demand_year = forms.ChoiceField(
        label='Select a Demand Year',
        initial='2023',
        required=True,
        widget=forms.Select(attrs={'class': 'form_input'})
    )
    
    scenario = forms.ModelChoiceField(
        queryset=Scenarios.objects.all().values_list('title', flat=True), # type: ignore
        empty_label=None,
        label='Select a Scenario',
        initial='Current',
        to_field_name='title',
        widget=forms.Select(attrs={'class': 'form_input'})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        year_choices = [(year, year) for year in TechnologyYears.objects.values_list('year', flat=True).distinct()]
        self.fields['weather_year'].choices = [(year, '20' + str(year)) for year in range(24, 25)] 
        self.fields['demand_year'].choices = year_choices

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

class SettingsForm(forms.Form):
    new_parameter = forms.CharField(max_length=45, label='New Parameter', required=False)
    new_value = forms.CharField(max_length=300, label='New Value', required=False)

    def __init__(self, *args, **kwargs):
        self.settings = kwargs.pop('settings', [])
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Div(
                Field('new_parameter', css_class='form-control'),
                Field('new_value', css_class='form-control'),
                css_class='form-group'
            )
        )

        for setting in self.settings:
            self.fields[f'field_{setting.idsettings}'] = forms.CharField(
                max_length=300,
                label=setting.parameter,
                initial=setting.value,
                required=False
            )
            self.fields[f'delete_{setting.idsettings}'] = forms.BooleanField(
                label='Delete',
                required=False
            )
            self.helper.layout.fields.append(Div(
                Field(f'field_{setting.idsettings}', css_class='form-control'),
                Field(f'delete_{setting.idsettings}', css_class='form-control'),
                css_class='form-group'
            ))

        self.helper.layout.append(FormActions(
            Submit('submit', 'Submit', css_class='btn btn-primary')
        ))

class ReferenceForm(forms.ModelForm):
    """Form for creating and editing references"""
    
    class Meta:
        model = Reference
        fields = [
            'source', 'title', 'author', 'publication_date', 
            'location', 'section', 'reference_type', 'notes', 
            'tags', 'is_active'
        ]
        widgets = {
            'publication_date': DateTimeInput(attrs={'type': 'datetime-local'}),
            'notes': forms.Textarea(attrs={'rows': 4}),
            'source': forms.TextInput(attrs={'size': 60}),
            'location': forms.URLInput(attrs={'size': 60}),
            'tags': forms.TextInput(attrs={
                'placeholder': 'research, api, documentation (comma-separated)'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make source field required
        self.fields['source'].required = True
        # Add CSS classes for styling
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'