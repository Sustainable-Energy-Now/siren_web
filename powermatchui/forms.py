# forms.py
from django import forms
from siren_web.models import Scenarios, Technologies, variations
from django.template.loader import render_to_string
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Div, Field

class DemandYearScenario(forms.Form):
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
    def __init__(self, *args, **kwargs):
        technologies = kwargs.pop('technologies')
        super(RunBatchForm, self).__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.fields['iterations'] = forms.IntegerField(required=True)

        variations_list = variations.objects.values_list('variation_name', flat=True)
        variations_choices = [(variation, variation) for variation in variations_list]
        variations_choices.append(('new', 'Create a new variation'))
        self.fields['variation'] = forms.ChoiceField(choices=variations_choices, required=True)

        self.fields['variation_name'] = forms.CharField(max_length=45, required=False)

        form_fields = []
        for technology, values in technologies.items():
            tech_key = f"{technology}"
            tech_name = values[0]
            display_fields = [
                Field(f"capacity_{tech_key}", readonly=True, css_class='form-group col-md-2', label=f"Capacity for {tech_name}", value=values[1]),
                Field(f"multiplier_{tech_key}", readonly=True, css_class='form-group col-md-2', label=f"Multiplier for {tech_name}", value=values[2]),
                Field(f"capex_{tech_key}", readonly=True, css_class='form-group col-md-2', label=f"Capex for {tech_name}", value=values[3]),
                Field(f"fom_{tech_key}", readonly=True, css_class='form-group col-md-2', label=f"FOM for {tech_name}", value=values[4]),
                Field(f"vom_{tech_key}", readonly=True, css_class='form-group col-md-2', label=f"VOM for {tech_name}", value=values[5]),
                Field(f"lifetime_{tech_key}", readonly=True, css_class='form-group col-md-2', label=f"Lifetime for {tech_name}", value=values[6]),
                Field(f"discount_rate_{tech_key}", readonly=True, css_class='form-group col-md-2', label=f"Discount Rate for {tech_name}", value=values[7]),
                Field(f"step_{tech_key}", css_class='form-group col-md-2'),
                Field(f"dimension_{tech_key}", css_class='form-group col-md-2'),
            ]
            form_fields.extend(display_fields)

        self.helper.layout = Layout(
            Div(
                Field('iterations', css_class='form-group col-md-4'),
                Field('variation', css_class='form-group col-md-4'),
                Field('variation_name', css_class='form-group col-md-4'),
                css_class='form-row'
            ),
            *form_fields
        )
        
    def clean(self):
        cleaned_data = super().clean()
        variation = cleaned_data.get('variation')
        variation_name = cleaned_data.get('variation_name')

        if variation == 'new' and not variation_name:
            self.add_error('variation_name', 'Please provide a name for the new variation.')

        technology_fields = [field for field in cleaned_data.keys() if field.endswith('_step') or field.endswith('_dimension')]

        for tech_field in technology_fields:
            tech_key = tech_field.split('_')[1]
            step_field = f"step_{tech_key}"
            dimension_field = f"dimension_{tech_key}"

            if cleaned_data.get(step_field) and cleaned_data.get(dimension_field):
                self.add_error(step_field, 'Only one of step or dimension should be specified for each technology.')
                self.add_error(dimension_field, 'Only one of step or dimension should be specified for each technology.')
                break
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
