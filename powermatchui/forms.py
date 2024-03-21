# forms.py
from django import forms
from siren_web.models import Scenarios, Technologies, variations
from django.template.loader import render_to_string
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Div, Field, Fieldset, Submit, HTML, Button, Row, Column, ButtonHolder
from crispy_bootstrap5.bootstrap5 import Accordion
from crispy_forms.bootstrap import AccordionGroup, FormActions

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
        DIMENSION_CHOICES = [
            ('capacity', 'Capacity'),
            ('multiplier', 'Multiplier'),
            ('capex', 'Capex'),
            ('fom', 'FOM'),
            ('vom', 'VOM'),
            ('lifetime', 'Lifetime'),
            ('discount_rate', 'Discount Rate'),
        ]
        technologies = kwargs.pop('technologies')
        super(RunBatchForm, self).__init__(*args, **kwargs)

        self.fields['iterations'] = forms.IntegerField(required=True)

        variations_list = variations.objects.values_list('variation_name', flat=True)
        variations_choices = [(variation, variation) for variation in variations_list]
        variations_choices.append(('new', 'Create a new variation'))
        self.fields['variation'] = forms.ChoiceField(choices=variations_choices, required=True)

        self.fields['variation_name'] = forms.CharField(
            max_length=45, required=False,
            widget=forms.TextInput(attrs={'style': 'display: block'}),
            )

        accordion_groups = []
        for technology in technologies:
            tech_key = f"{technology.pk}"
            tech_name = technology.technology_name
            self.fields[f"capacity_{tech_key}"] = forms.Field(initial=technology.capacity, label=f"Capacity")
            self.fields[f"mult_{tech_key}"] = forms.Field(initial=technology.mult, label=f"Multiplier")
            self.fields[f"capex_{tech_key}"] = forms.FloatField(initial=technology.capex, label=f"Capex")
            self.fields[f"fom_{tech_key}"] = forms.FloatField(initial=technology.fom, label=f"FOM")
            self.fields[f"vom_{tech_key}"] = forms.FloatField(initial=technology.vom, label=f"VOM")            
            self.fields[f"lifetime_{tech_key}"] = forms.FloatField(initial=technology.lifetime, label=f"Lifetime")
            self.fields[f"discount_rate_{tech_key}"] = forms.FloatField(initial=technology.discount_rate, label=f"Discount Rate", required=False)
            self.fields[f"step_{tech_key}"] = forms.FloatField(label=f"Step", required=False)
            self.fields[f"dimension_{tech_key}"] = forms.ChoiceField(
                choices=DIMENSION_CHOICES,
                label=f"Dimension",
                required=False
            )
            accordion_group_fields = [
                # Div(f"{tech_name} details",
                Div(Field(f"capacity_{tech_key}", readonly=True, css_class='row col-md-4'),
                    Field(f"mult_{tech_key}", readonly=True, css_class='row col-md-4'),
                    Field(f"capex_{tech_key}", readonly=True, css_class='row col-md-4'),
                    Field(f"fom_{tech_key}", readonly=True, css_class='row col-md-4'),
                    Field(f"vom_{tech_key}", readonly=True, css_class='row col-md-4'),
                    Field(f"lifetime_{tech_key}", readonly=True, css_class='row col-md-4'),
                    Field(f"discount_rate_{tech_key}", readonly=True, css_class='row col-md-4'),
                    HTML("<hr>"),
                ),
                Div(
                    HTML('<legend>Step and Dimension</legend>'),
                    Row(
                        Field(f"step_{tech_key}", css_class='col-md-4'),
                        Field(f"dimension_{tech_key}", css_class='col-md-4'),
                    ),
                    css_class='row',
                ),
                HTML("<hr>")
            ]
            
            accordion_groups.append(AccordionGroup(f"{tech_name} Details", *accordion_group_fields)) 
        self.helper = FormHelper()
        self.helper.form_action = '/batch/'
        self.helper.layout = Layout(
            Div(
                Field('iterations', css_class='row col-md-4'),
                Field('variation', css_class='row col-md-4'),
                Field('variation_name', css_class='row col-md-4'),
                css_class='row',
            ),
            Accordion(*accordion_groups),
            FormActions(
                Submit('submit', 'Submit'),
            )
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
            
            step_value = cleaned_data.get(step_field)
            dimension_value = cleaned_data.get(dimension_field)
            
            if (step_value and not dimension_value) or (dimension_value and not step_value):
                self.add_error(step_field, 'Both step and dimension must be specified for a technology.')
                self.add_error(dimension_field, 'Both step and dimension must be specified for a technology.')
                break
        return cleaned_data

class RunOptimisationForm(forms.Form):
    LEVEL_OF_DETAIL_CHOICES = [
    ('Summary', 'Summary'),
    ('Detailed', 'Detailed'),
    ]
    
    level_of_detail = forms.ChoiceField(choices=LEVEL_OF_DETAIL_CHOICES, initial='Summary', widget=forms.RadioSelect)