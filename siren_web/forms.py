# forms.py
from django import forms
from django.conf import settings
from django.forms.widgets import DateTimeInput
from siren_web.models import Scenarios, TechnologyYears, facilities
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Div, Field, Submit
from crispy_forms.bootstrap import FormActions
from .models import Reference, ReferenceAttribute


def get_weather_year_choices():
    """
    Weather years that have wind data, newest first: the wind_weather/<year>/ folders that hold
    at least one file SAM can read (the same rules the weather-file finder applies).
    """
    # Imported here: the processor pulls in PySAM, which forms.py shouldn't load at import time.
    from powermapui.views.sam_resource_processor import WeatherFileFinder
    return [(year, year) for year in WeatherFileFinder.available_years(settings.WEATHER_DATA_DIR, 'wind')]

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
        initial='2024',
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
        self.fields['weather_year'].choices = get_weather_year_choices()
        self.fields['demand_year'].choices = year_choices


class WeatherScenarioSettings(DemandScenarioSettings):
    """
    Same as DemandScenarioSettings (weather year + scenario) but without
    the Demand Year field -- used wherever the app derives its own year at
    run time from whichever Load facility is actually supplying demand
    (see siren_web.database_operations.resolve_baseline_year) rather than
    having the user pick one up front. Used by PowermatchUIHomeView and
    PowermapUIHomeView, plus the individual powermapui dashboard views
    (cel_map, infrastructure_network, pipeline_gantt/waterfall) that embed
    their own local weather/scenario settings form. powerplotui keeps the
    full DemandScenarioSettings form since it still uses
    session['demand_year'] for unrelated lookups, and powermapui's own
    technologies_views.technologies page keeps its own separate
    DemandYearForm (below) since that page is a genuine year-by-year
    technology cost/capacity browser, not a derived-year consumer.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        del self.fields['demand_year']


class DemandScenarioOverrideForm(forms.Form):
    """
    Lets the user pick which AEMO/ESOO (or EV-layered) demand-forecast
    scenario's Load trace to use, independently of session['scenario']
    (the supply/facilities Scenario). Used by powermatchui's Baseline
    Scenario page (a per-run dispatch override -- see
    siren_web.database_operations.resolve_demand_override) and by
    powermapui's Run Power page (which year's TechnologyYears data to
    generate against -- see resolve_baseline_year). Selecting a facility
    here never changes any ScenariosFacilities/ScenariosTechnologies row.
    """
    demand_scenario_facility = forms.ModelChoiceField(
        queryset=facilities.objects.filter(
            idtechnologies__technology_name='Load',
            scenarios__interval_minutes=30,
        ).distinct().order_by('facility_name'),
        required=False,
        empty_label="Use the supply scenario's own Load (default)",
        label='AEMO/ESOO Demand Forecast',
        widget=forms.Select(attrs={'class': 'form_input'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['demand_scenario_facility'].label_from_instance = lambda f: f.facility_name

        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Field('demand_scenario_facility'),
        )


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


class ReferenceAttributeForm(forms.ModelForm):
    """Form for linking a Reference to a model attribute"""

    class Meta:
        model = ReferenceAttribute
        fields = ['model_name', 'attribute_name', 'description']
        widgets = {
            'model_name': forms.TextInput(attrs={'placeholder': 'e.g. Scenarios'}),
            'attribute_name': forms.TextInput(attrs={'placeholder': 'e.g. capacity'}),
            'description': forms.TextInput(attrs={'placeholder': 'How this reference provides this data'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'