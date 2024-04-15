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
        choices=[('2022', '2022'), ('2022', '2022')],
        label='Select a Demand Year',
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

class BaselineScenarioForm(forms.Form):
    carbon_price = forms.DecimalField(label='Carbon Price', required=False)
    discount_rate = forms.DecimalField(label='Discount Rate', required=False)

    def __init__(self, *args, **kwargs):
        self.technologies = kwargs.pop('technologies', [])
        self.carbon_price = kwargs.pop('carbon_price', None)
        self.discount_rate = kwargs.pop('discount_rate', None)
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout()
        
        # Create fields for Carbon Price and Discount Rate
        self.fields['carbon_price'] = forms.DecimalField(
            label='Carbon Price',
            initial=self.carbon_price,
            required=False
        )
        self.fields['discount_rate'] = forms.DecimalField(
            label='Discount Rate',
            initial=self.discount_rate,
            required=False
        )
        self.helper.layout.fields.append(Div(
            Field('carbon_price', css_class='form-control'),
            Field('discount_rate', css_class='form-control'),
            css_class='form-group'
        ))
        
        # Create fields for each technology
        for technology in self.technologies:
            tech_key = f"{technology.pk}"
            field_name = f'capacity_{tech_key}'
            self.fields[field_name] = forms.DecimalField(
                label=technology.technology_name,
                initial=technology.capacity,
                required=False
            )
            self.helper.layout.fields.append(Div(
                Field(field_name, css_class='form-control'),
                css_class='form-group'
            ))
            
        self.helper.layout.append(FormActions(
            Submit('save', 'Save Runtime Parameters', css_class='btn btn-primary')
        ))

class ExtractTechnologiesForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super(ExtractTechnologiesForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_action = '/extract_technologies/'
        self.helper.layout = Layout(
            FormActions(
                Submit('submit', 'Extract Technologies'),
            )
        )
class RunPowermatchForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super(RunPowermatchForm, self).__init__(*args, **kwargs)
        LEVEL_OF_DETAIL_CHOICES = [
        ('Summary', 'Summary'),
        ('Detailed', 'Detailed'),
        ]
        
        self.fields['level_of_detail'] = forms.ChoiceField(
            choices=LEVEL_OF_DETAIL_CHOICES,
            initial='Summary',
            widget=forms.RadioSelect,
            required=False  # Make the field optional
            )
        self.fields['save_baseline'] = forms.BooleanField(
            label='Save Baseline',
            initial=False,
            required=False
            )
        
        self.helper = FormHelper()
        self.helper.form_action = '/run_baseline/'
        self.helper.layout = Layout(
            Field('level_of_detail'),
            Field('save_baseline'),
            FormActions(
                Submit('submit', 'Run Powermatch',  css_class='btn btn-primary'),
            )
        )

class RunVariationForm(forms.Form):
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
        variation_data = kwargs.pop('variation_data', None)
        
        super(RunVariationForm, self).__init__(*args, **kwargs)
        if variation_data:
            self.fields['stages'] = forms.IntegerField(required=True, initial=variation_data.get('stages'))
            self.fields['variation_name'] = forms.CharField(
                required=True,
                widget=forms.HiddenInput(),
                initial=variation_data.get('variation_name'),
            )
        else:
            self.fields['stages'] = forms.IntegerField(required=True)
            self.fields['variation_name'] = forms.CharField(
                required=True,
                widget=forms.HiddenInput(),
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
            if variation_data and variation_data.get('variation_name') != 'new' and \
                variation_data.get('idtechnologies').idtechnologies == int(tech_key):
                dimension_value = variation_data.get('dimension')
                self.fields[f"dimension_{tech_key}"] = forms.ChoiceField(
                    choices=DIMENSION_CHOICES,
                    label=f"Dimension",
                    required=False,
                    initial=dimension_value if dimension_value else ''
                )
                self.fields[f"step_{tech_key}"] = forms.FloatField(initial=variation_data.get('step'), label=f"Step", required=False)
            else:
                self.fields[f"dimension_{tech_key}"] = forms.ChoiceField(
                    choices=DIMENSION_CHOICES,
                    label=f"Dimension",
                    required=False
                )
                self.fields[f"step_{tech_key}"] = forms.FloatField(label=f"Step", required=False)
                
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
        self.helper.form_action = '/variations/'
        self.helper.layout = Layout(
            Field('stages', css_class='row col-md-4'),
            Field('variation_name', id='batch_variation_name_field'),
            Accordion(*accordion_groups),
            FormActions(
                Submit('submit', 'Submit'),
            )
        )
        
    def clean(self):
        cleaned_data = super().clean()
        updated_data= {}
        updated_data['variation_name'] = self.cleaned_data.get('variation_name')
        updated_data['stages'] = self.cleaned_data.get('stages')
        technology_fields = [field for field in cleaned_data.keys() if field.startswith('step_') or field.startswith('dimension_')]
        
        updated_technologies = {}
        
        for tech_field in technology_fields:
            tech_key = tech_field.split('_')[1]
            step_field = f"step_{tech_key}"
            dimension_field = f"dimension_{tech_key}"
            
            step_value = cleaned_data.get(step_field)
            dimension_value = cleaned_data.get(dimension_field)
            
            if step_value and dimension_value:
                updated_data['step'] = step_value
                updated_data['dimension'] = dimension_value
                updated_data['idtechnologies'] = tech_key

        return updated_data

class RunOptimisationForm(forms.Form):
    LEVEL_OF_DETAIL_CHOICES = [
    ('Summary', 'Summary'),
    ('Detailed', 'Detailed'),
    ]
    
    level_of_detail = forms.ChoiceField(
        choices=LEVEL_OF_DETAIL_CHOICES, 
        initial='Summary', widget=forms.RadioSelect
        )

class SelectVariationForm(forms.Form):
    def __init__(self, *args, **kwargs):
        selected_variation = kwargs.pop('selected_variation', None)
        super(SelectVariationForm, self).__init__(*args, **kwargs)
        variations_queryset = variations.objects.all()
        variations_list = [variation.variation_name for variation in variations_queryset]
        variation_description_dict = {variation.variation_name: variation.variation_description for variation in variations_queryset}

        variations_choices = [('Baseline', 'Baseline')] + [(variation_name, variation_name) for variation_name in variations_list]
        variations_choices.append(('new', 'Create a new variant'))

        self.fields['variation_name'] = forms.ChoiceField(choices=variations_choices, required=True)

        if selected_variation:  # if a variation is passed set it as selected
            self.fields['variation_name'].initial = selected_variation
            if selected_variation != 'Baseline' and selected_variation != 'new':
                self.fields['variation_description'] = forms.CharField(
                    max_length=250,
                    required=False,
                    widget=forms.TextInput(attrs={'readonly': True}),
                    initial=variation_description_dict.get(selected_variation, '')
                )
        else:
            self.fields['variation_name'].initial = 'Baseline'
            self.fields['variation_description'] = forms.CharField(
                max_length=250,
                required=False,
                widget=forms.TextInput(attrs={'readonly': True})
            )
        
        self.helper = FormHelper()
        self.helper.form_action = '/variation/'
        self.helper.layout = Layout(
            Div(
                Field('variation_name', css_class='row col-md-4'),
                css_class='row', id='variation_name_field'
            ),
        )
        if selected_variation != 'Baseline' and selected_variation != 'new':
            self.helper.layout.fields.append(Div(
                    Field('variation_description', css_class='row col-md-4'),
                    css_class='row',
                )
            )
        self.helper.layout.append(FormActions(
            Submit('refresh', 'Refresh', css_class='btn btn-primary')
        ))
