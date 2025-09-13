# forms.py
import configparser
from decimal import Decimal
from django import forms
from django.conf import settings
from siren_web.models import Scenarios, TechnologyYears, variations
from django.template.loader import render_to_string
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Div, Field, Fieldset, Submit, HTML, Button, Row, Column, ButtonHolder
from crispy_bootstrap5.bootstrap5 import Accordion
from crispy_forms.bootstrap import AccordionGroup, FormActions
import json
import os

import os
from django.conf import settings

class DemandScenarioSettings(forms.Form):
    year_choices = [(year, year) for year in TechnologyYears.objects.values_list('year', flat=True).distinct()]
    
    demand_year = forms.ChoiceField(
        choices=year_choices,
        label='Select a Demand Year',
        initial='2023',
        required=True,
        widget=forms.Select(attrs={'class': 'form_input'})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    scenario = forms.ModelChoiceField(
        queryset=Scenarios.objects.all().values_list('title', flat=True),
        empty_label=None,
        label='Select a Scenario',
        initial='Current',
        to_field_name='title',
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
        self.helper.layout.fields.append(
            Div(
                HTML("<hr>"),
                Row(
                    Column('carbon_price', css_class='form-group col-md-6 mb-0'),
                    Column('discount_rate', css_class='form-group col-md-6 mb-0'),
                    css_class='form-row'
                    )
                ),
            )
       
        # Create fields for each technology with capacity, multiplier, and product
        rows = []
        current_row = []
        
        # Add header row
        header_row = HTML("""
            <div class="row form-row">
                <div class="col-md-3"><strong>Technology</strong></div>
                <div class="col-md-3"><strong>Capacity</strong></div>
                <div class="col-md-3"><strong>Multiplier</strong></div>
                <div class="col-md-3"><strong>Product</strong></div>
            </div>
        """)
        self.helper.layout.append(header_row)
        
        for i, technology in enumerate(self.technologies):
            tech_key = f"{technology.pk}"
            
            # Create hidden field for capacity (read-only)
            capacity_field_name = f'capacity_{tech_key}'
            self.fields[capacity_field_name] = forms.DecimalField(
                initial=technology.capacity, 
                required=False,
                widget=forms.HiddenInput()
            )
            
            # Create field for multiplier (editable)
            multiplier_field_name = f'multiplier_{tech_key}'
            self.fields[multiplier_field_name] = forms.DecimalField(
                initial=technology.mult or 1.0, 
                required=False,
                widget=forms.NumberInput(attrs={
                    'class': 'form-control multiplier-input',
                    'data-tech-id': tech_key,
                    'step': '0.01'
                })
            )
            
            # Calculate product for display
            product_value = (technology.capacity or 0) * (technology.mult or 1.0)
            
            # Create a row for this technology
            tech_row = HTML(f"""
                <div class="row form-row">
                    <div class="col-md-3">
                        <label class="form-label">{technology.technology_name}</label>
                    </div>
                    <div class="col-md-3">
                        <input type="text" class="form-control" value="{technology.capacity or 0:.2f}" readonly>
                    </div>
                    <div class="col-md-3">
                        {{% field '{multiplier_field_name}' %}}
                    </div>
                    <div class="col-md-3">
                        <input type="text" class="form-control product-display" 
                               id="product_{tech_key}" 
                               value="{product_value:.2f}" 
                               readonly>
                    </div>
                </div>
            """)
            
            rows.append(tech_row)
            
            # Add the hidden capacity field
            rows.append(Field(capacity_field_name))

        self.helper.layout.extend([
            HTML("<hr>"),
            *rows,
            HTML("<hr>"),
            # Add JavaScript for real-time calculation
            HTML("""
                <script>
                document.addEventListener('DOMContentLoaded', function() {
                    const multiplierInputs = document.querySelectorAll('.multiplier-input');
                    
                    multiplierInputs.forEach(function(input) {
                        input.addEventListener('input', function() {
                            const techId = this.getAttribute('data-tech-id');
                            const capacityInput = document.querySelector(`input[name="capacity_${techId}"]`);
                            const productDisplay = document.getElementById(`product_${techId}`);
                            
                            if (capacityInput && productDisplay) {
                                const capacity = parseFloat(capacityInput.value) || 0;
                                const multiplier = parseFloat(this.value) || 0;
                                const product = capacity * multiplier;
                                
                                productDisplay.value = product.toFixed(2);
                            }
                        });
                    });
                });
                </script>
            """),
            FormActions(
                Submit('save', 'Save Runtime Parameters', css_class='btn btn-primary')
            )
        ])

    def clean(self):
        cleaned_data = super().clean()
        # Validate carbon_price
        carbon_price = cleaned_data.get('carbon_price')
        if carbon_price is None:
            self.add_error('carbon_price', 'This field is required.')

        # Validate discount_rate
        discount_rate = cleaned_data.get('discount_rate')
        if discount_rate is None:
            self.add_error('discount_rate', 'This field is required.')

        # Validate multiplier for each technology
        for technology in self.technologies:
            tech_key = f"{technology.pk}"
            multiplier_field_name = f'multiplier_{tech_key}'
            multiplier = cleaned_data.get(multiplier_field_name)
            if multiplier is None:
                self.add_error(multiplier_field_name, 'This field is required.')
                
        return cleaned_data

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
            ('multiplier', 'Multiplier'),
            ('capex', 'Capex'),
            ('fom', 'FOM'),
            ('vom', 'VOM'),
            ('lifetime', 'Lifetime'),
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
        for key, value in technologies.items():
            # Create a field for each technology
            tech_name = key
            if tech_name == 'Load':
                continue
            technology = value
            tech_key = f"{technology.tech_id}"
            self.fields[f"mult_{tech_key}"] = forms.Field(initial=technology.multiplier, label=f"Multiplier")
            self.fields[f"capex_{tech_key}"] = forms.FloatField(initial=technology.capex, label=f"Capex")
            self.fields[f"fom_{tech_key}"] = forms.FloatField(initial=technology.fixed_om, label=f"FOM")
            self.fields[f"vom_{tech_key}"] = forms.FloatField(initial=technology.variable_om, label=f"VOM")            
            self.fields[f"lifetime_{tech_key}"] = forms.FloatField(initial=technology.lifetime, label=f"Lifetime")
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
                Div(Field(f"mult_{tech_key}", readonly=True, css_class='row col-md-4'),
                    Field(f"capex_{tech_key}", readonly=True, css_class='row col-md-4'),
                    Field(f"fom_{tech_key}", readonly=True, css_class='row col-md-4'),
                    Field(f"vom_{tech_key}", readonly=True, css_class='row col-md-4'),
                    Field(f"lifetime_{tech_key}", readonly=True, css_class='row col-md-4'),
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

class OptimisationForm(forms.Form):
    def __init__(self, *args, **kwargs):
        self.scenario_settings = kwargs.pop('scenario_settings', [])
        self.optimisation_data = kwargs.pop('optimisation_data', [])
        super(OptimisationForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.fields['choice'] = forms.ChoiceField(
            choices=[
                ('LCOE', 'LCOE'), 
                ('Multi', 'Multi'), 
                ('Both', 'Both')
            ], 
            label='Optimisation Choice',
            initial=self.scenario_settings['choice']
        )

        self.fields['optGenn'] = forms.FloatField(label='Number of Generations', initial=self.scenario_settings['optGenn'])
        self.fields['optPopn'] = forms.FloatField(label='Population size', initial=self.scenario_settings['optPopn'])
        self.fields['optLoad'] = forms.FloatField(label='Adjust Load', initial=self.scenario_settings['optLoad'])
        self.fields['MutnProb'] = forms.FloatField(label='Mutation Probability', initial=self.scenario_settings['MutnProb'])
        self.fields['optStop'] = forms.FloatField(label='Exit if Stable', initial=self.scenario_settings['optStop'])
        self.helper.layout = Layout(
            HTML("<hr>"),
            Row(
                Column('choice', css_class='form-group col-md-3 mb-0'),
                Column('optGenn', css_class='form-group col-md-3 mb-0'),
                Column('optPopn', css_class='form-group col-md-3 mb-0'),
                css_class='form-row'
            ),
            Row(
                Column('optLoad', css_class='form-group col-md-3 mb-0'),
                Column('MutnProb', css_class='form-group col-md-3 mb-0'),
                Column('optStop', css_class='form-group col-md-3 mb-0'),
                css_class='form-row'
            ),
        )
        self.lcoe = self.scenario_settings['lcoe'].split(',')
        self.fields['LCOE_Weight'] = forms.FloatField(label='LCOE Weight', initial=self.lcoe[0])
        self.fields['LCOE_Better']  = forms.FloatField(label='LCOE Better', initial=self.lcoe[1])
        self.fields['LCOE_Worse']  = forms.FloatField(label='LCOE Worse', initial=self.lcoe[2])
        self.load_pct  = self.scenario_settings['load_pct'].split(',')
        self.fields['Load_Weight']  = forms.FloatField(label='Load Weight', initial=self.load_pct[0])
        self.fields['Load_Better']  = forms.FloatField(label='Load Better', initial=self.load_pct[1])
        self.fields['Load_Worse']  = forms.FloatField(label='Load Worse', initial=self.load_pct[2])
        self.surplus = self.scenario_settings['surplus'].split(',')
        self.fields['Surplus_Weight']  = forms.FloatField(label='Surplus Weight', initial=self.surplus[0])
        self.fields['Surplus_Better']  = forms.FloatField(label='Surplus Better', initial=self.surplus[1])
        self.fields['Surplus_Worse']  = forms.FloatField(label='Surplus Worse', initial=self.surplus[2])
        self.re_pct  = self.scenario_settings['re_pct'].split(',')
        self.fields['RE_Weight']  = forms.FloatField(label='RE Weight', initial=self.re_pct[0])
        self.fields['RE_Better']  = forms.FloatField(label='RE Better', initial=self.re_pct[1])
        self.fields['RE_Worse']  = forms.FloatField(label='RE Worse', initial=self.re_pct[2])
        self.cost = self.scenario_settings['cost'].split(',')
        self.fields['Cost_Weight']  = forms.FloatField(label='Cost Weight', initial=self.cost[0])
        self.fields['Cost_Better']  = forms.FloatField(label='Cost Better', initial=self.cost[1])
        self.fields['Cost_Worse']  = forms.FloatField(label='Cost Worse', initial=self.cost[2])
        self.co2  = self.scenario_settings['co2'].split(',')
        self.fields['CO2_Weight']  = forms.FloatField(label='CO2 Weight', initial=self.co2[0])
        self.fields['CO2_Better']  = forms.FloatField(label='CO2 Better', initial=self.co2[1])
        self.fields['CO2_Worse']  = forms.FloatField(label='CO2 Worse', initial=self.co2[2])

        self.helper.layout.extend([
            HTML("<hr>"),
            Row(
                Column('LCOE_Weight', 'LCOE_Better', 'LCOE_Worse', css_class='form-group col-md-4 mb-0'),
                Column('Load_Weight', 'Load_Better', 'Load_Worse', css_class='form-group col-md-4 mb-0'),
                Column('Surplus_Weight', 'Surplus_Better', 'Surplus_Worse', css_class='form-group col-md-4 mb-0'),
                css_class='form-row'
            ),
            Row(
                Column('RE_Weight', 'RE_Better', 'RE_Worse', css_class='form-group col-md-4 mb-0'),
                Column('Cost_Weight', 'Cost_Better', 'Cost_Worse', css_class='form-group col-md-4 mb-0'),
                Column('CO2_Weight', 'CO2_Better', 'CO2_Worse', css_class='form-group col-md-4 mb-0'),
                css_class='form-row'
            ),
        ])

        # Create fields for Optimisation model
        optimisation_rows = []
        current_row = []
        for i, optimisation in enumerate(self.optimisation_data):
            tech_key = f"{optimisation['idtechnologies']}"
            self.fields[f'approach_{tech_key}'] = forms.CharField(
                label=f"{optimisation['technology_name']} Approach",
                initial=optimisation['approach'],
                required=False
            )
            self.fields[f'capacity_{tech_key}'] = forms.FloatField(
                label=f"{optimisation['technology_name']} Capacity",
                initial=optimisation['capacity'],
                required=False
            )
            self.fields[f'capacity_max_{tech_key}'] = forms.FloatField(
                label=f"{optimisation['technology_name']} Max Capacity",
                initial=optimisation['capacity_max'],
                required=False
            )
            self.fields[f'capacity_min_{tech_key}'] = forms.FloatField(
                label=f"{optimisation['technology_name']} Min Capacity",
                initial=optimisation['capacity_min'],
                required=False
            )
            self.fields[f'capacity_step_{tech_key}'] = forms.FloatField(
                label=f"{optimisation['technology_name']} Capacity Step",
                initial=optimisation['capacity_step'],
                required=False
            )
            self.fields[f'capacities_{tech_key}'] = forms.FloatField(
                label=f"{optimisation['technology_name']} Capacities",
                initial=optimisation['capacities'],
                required=False
            )
            current_row.append(Column(
                Field(f'approach_{tech_key}', css_class='form-control'),
                Field(f'capacity_{tech_key}', css_class='form-control'),
                Field(f'capacity_max_{tech_key}', css_class='form-control'),
                Field(f'capacity_min_{tech_key}', css_class='form-control'),
                Field(f'capacity_step_{tech_key}', css_class='form-control'),
                Field(f'capacities_{tech_key}', css_class='form-control'),
                css_class='form-group col-md-6 mb-0')
            )

            if (i + 1) % 2 == 0 or i == len(self.optimisation_data) - 1:
                optimisation_rows.append(Row(*current_row, css_class='form-row'))
                current_row = []

        self.helper.form_action = '/optimisation/'
        self.helper.layout.extend([
            HTML("<hr>"),
            *optimisation_rows,
            HTML("<hr>"),
            FormActions(
                Submit('save', 'Save Runtime Parameters', css_class='btn btn-primary')
            )
        ])

    def clean(self):
        cleaned_data = super().clean()
        choice = cleaned_data.get('choice')
        optGenn = cleaned_data.get('optGenn')
        optPopn = cleaned_data.get('optPopn')
        optLoad = cleaned_data.get('optLoad')
        MutnProb = cleaned_data.get('MutnProb')
        optStop = cleaned_data.get('optStop')

        # Validate input fixed fields
        LCOE_Weight = cleaned_data.get('LCOE_Weight')
        LCOE_Better= cleaned_data.get('LCOE Better')
        LCOE_Worse = cleaned_data.get('LCOE Worse')

        Load_Weight = cleaned_data.get('Load_Weight')
        Load_Better = cleaned_data.get('Load_Better')
        Load_Worse = cleaned_data.get('Load_Worse')

        Surplus_Weight = cleaned_data.get('Surplus_Weight')
        Surplus_Better = cleaned_data.get('Surplus_Better')
        Surplus_Worse = cleaned_data.get('Surplus_Worse')

        RE_Weight = cleaned_data.get('RE_Weight')
        RE_Better = cleaned_data.get('RE_Better')
        RE_Worse = cleaned_data.get('RE_Worse')

        Cost_Weight = cleaned_data.get('Cost_Weight')
        Cost_Better = cleaned_data.get('Cost_Better')
        Cost_Worse = cleaned_data.get('Cost_Worse')

        CO2_Weight = cleaned_data.get('CO2_Weight')
        CO2_Better = cleaned_data.get('CO2_Better')
        CO2_Worse = cleaned_data.get('CO2_Worse')
        # if CO2_Weight is None:
        #     self.add_error('CO2_Weight', 'This field is required.')
        # Validate optimisation fields
        for optimisation in self.optimisation_data:
            tech_key = f"{optimisation['idtechnologies']}"
            approach_fn = f'approach_{tech_key}'
            approach = cleaned_data.get(approach_fn)
            capacity_fn = f'capacity_{tech_key}'
            capacity = cleaned_data.get(capacity_fn)
            if capacity is None:
                self.add_error(capacity_fn, 'This field is required.')
            capacity_max_fn = f'capacity_{tech_key}'
            capacity_max = cleaned_data.get(capacity_max_fn)
            capacity_min_fn = f'capacity_{tech_key}'
            capacity_min = cleaned_data.get(capacity_min_fn)
            capacity_step_fn = f'capacity_{tech_key}'
            capacity_step = cleaned_data.get(capacity_step_fn)
            capacities_fn = f'capacity_{tech_key}'
            capacities = cleaned_data.get(capacities_fn)
        return cleaned_data
    
class SelectVariationForm(forms.Form):
    def __init__(self, *args, **kwargs):
        scenario = kwargs.pop('scenario', None)
        selected_variation = kwargs.pop('selected_variation', None)
        super(SelectVariationForm, self).__init__(*args, **kwargs)
        if scenario:
            variations_queryset = variations.objects.filter(idscenarios=scenario)
        else:
            variations_queryset = variations.objects.none()
        variations_list = [variation.variation_name for variation in variations_queryset]
        variation_description_dict = {variation.variation_name: variation.variation_description for variation in variations_queryset}

        variations_choices = [(variation_name, variation_name) for variation_name in variations_list]
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

class PowermatchForm(forms.Form):
    def __init__(self, *args, server_files=None, **kwargs):
        config_data = kwargs.pop('config_data', None)
        super().__init__(*args, **kwargs)
        
        # Get list of available server files
        self.server_files = server_files or []
        file_choices = [(f, f) for f in self.server_files]
        file_choices.insert(0, ('', '-- Select a file --'))
        gen_sheet_choices = [(item.strip(), item.strip()) for item in config_data['Powermatch']['generator_sheets'].split(',')]
        # File selection fields
        self.fields['constraints_file'] = forms.ChoiceField(
            label="Constraints File:",
            choices=file_choices,
            required=False,
            widget=forms.Select(attrs={
                'class': 'form-select server-file-select',
                'data-file-type': 'constraints'
            })
        )
        self.fields['constraints_sheet'] = forms.ChoiceField(
            label="Constraints Sheet:",
            choices=[("Constraints", "Constraints")],
            required=False,
            widget=forms.Select(attrs={'class': 'form-select'})
        )
        
        self.fields['generators_file'] = forms.ChoiceField(
            label="Generators File:",
            choices=file_choices,
            required=False,
            widget=forms.Select(attrs={
                'class': 'form-select server-file-select',
                'data-file-type': 'generators'
            })
        )

        self.fields['generators_sheet'] = forms.ChoiceField(
            label="Generators Sheet:",
            choices=gen_sheet_choices,
            required=False,
            widget=forms.Select(attrs={'class': 'form-select'})
        )
        
        self.fields['optimisation_file'] = forms.ChoiceField(
            label="Optimisation File:",
            choices=file_choices,
            required=False,
            widget=forms.Select(attrs={
                'class': 'form-select server-file-select',
                'data-file-type': 'optimisation'
            })
        )
        self.fields['optimisation_sheet'] = forms.ChoiceField(
            label="Optimisation Sheet:",
            choices=[("Optimisation_was", "Optimisation_was")],
            required=False,
            widget=forms.Select(attrs={'class': 'form-select'})
        )
        self.fields['data_file'] = forms.ChoiceField(
            label="Data File:",
            choices=file_choices,
            required=False,
            widget=forms.Select(attrs={
                'class': 'form-select server-file-select',
                'data-file-type': 'data'
            })
        )
        # Get available years for load_year choices
        years = self.get_available_years()
        self.fields['load_year'] = forms.ChoiceField(
            label="Load Year:",
            choices=[("n/a", "n/a")] + [(year, year) for year in years],
            required=False,
            widget=forms.Select(attrs={'class': 'form-select'}),
            help_text="(To use a different load year to the data file. Otherwise choose 'n/a')"
        )

        self.fields['results_prefix'] = forms.CharField(
            label="Results Prefix:",
            required=False,
            widget=forms.TextInput(attrs={'class': 'form-control'})
        )

        self.fields['results_file'] = forms.ChoiceField(
            label="Results File:",
            choices=file_choices,
            required=False,
            widget=forms.Select(attrs={
                'class': 'form-select server-file-select',
                'data-file-type': 'results'
            })        )
        
        self.fields['batch_file'] = forms.ChoiceField(
            label="Batch File:",
            choices=file_choices,
            required=False,
            widget=forms.Select(attrs={
                'class': 'form-select server-file-select',
                'data-file-type': 'batch'
            })
        )
        
        self.fields['replace_last'] = forms.BooleanField(
            label="Replace Last",
            required=False,
            initial=False,
            widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            help_text="(check to replace last Results worksheet in Batch spreadsheet)"
        )
        
        self.fields['prefix_facility'] = forms.BooleanField(
            label="Prefix facility names in Batch report:",
            required=False,
            initial=False,
            widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
        )
        
        self.fields['discount_rate'] = forms.DecimalField(
            label="Discount Rate:",
            max_digits=4,
            decimal_places=2,
            initial=7.00,
            widget=forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01'
            }),
            help_text="(%. Only required if using input costs rather than reference LCOE)"
        )
        
        self.fields['carbon_price'] = forms.DecimalField(
            label="Carbon Price:",
            max_digits=5,
            decimal_places=2,
            initial=0.00,
            widget=forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01'
            }),
            help_text="($/tCO2e. Use only if LCOE excludes carbon price)"
        )
        
        self.fields['adjust_generators'] = forms.BooleanField(
            label="Adjust Generators:",
            required=False,
            initial=False,
            widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            help_text="(check to adjust generators capacity data)"
        )

        self.fields['generator_columns'] = forms.CharField(
            widget=forms.HiddenInput(),
            required=False
        )
        # File upload field
        self.fields['new_file'] = forms.FileField(
            label="Upload New File",
            required=False,
            widget=forms.FileInput(attrs={
                'class': 'form-control',
                'data-url': '/upload-file/'  # URL for handling file uploads
            }),
            help_text="Upload a new file to the server"
        )
        # Set initial values from config if available
        if config_data and config_data.has_section('Powermatch'):
            try:
                # Map config sections to form fields
                config_mappings = {
                    'Powermatch': {
                        'constraints_file': 'constraints_file',
                        'constraints_sheet': 'constraints_sheet',
                        'generators_file': 'generators_file',
                        'generators_sheet': 'generators_sheet',
                        'optimisation_file': 'optimisation_file',
                        'optimisation_sheet': 'optimisation_sheet',
                        'data_file': 'data_file',
                        'results_file': 'results_file',
                        'batch_file': 'batch_file',
                        'replace_last': 'replace_last',
                        'prefix_facility': 'prefix_facility',
                        'discount_rate': 'discount_rate',
                        'carbon_price': 'carbon_price',
                        'adjust_generators': 'adjust_generators',
                        'generators_left_column': 'generator_columns',
                        'generators_sheet': 'generators_sheet',
                    }
                }

                # Update field values from config
                for section, fields in config_mappings.items():
                    if section in config_data:
                        for config_key, form_field in fields.items():
                            if config_key in config_data[section]:
                                value = config_data[section][config_key]
                                
                                # Handle boolean fields
                                if isinstance(self.fields[form_field], forms.BooleanField):
                                    value = value.lower() in ('true', '1', 'yes', 'on')
                                
                                # Handle decimal fields
                                elif isinstance(self.fields[form_field], forms.DecimalField):
                                    try:
                                        value = float(value)
                                    except (ValueError, TypeError):
                                        continue
                                # Set initial value for the field
                                if form_field == 'generator_columns':
                                    left_generators = config_data['Powermatch'].get('generators_left_column', '')
                                    initial_left_column = [item.strip() for item in left_generators.split(',')]
                                    right_generators = config_data['Powermatch'].get('generators_right_column', '')
                                    initial_right_column = [item.strip() for item in right_generators.split(',')]
                                else:
                                    self.fields[form_field].initial = value

                # Store the initial values in the form
                self.initial_generator_columns = {
                    'leftColumn': initial_left_column,
                    'rightColumn': initial_right_column
}
            except Exception as e:
                # Log the error but don't prevent form from loading
                print(f"Error initializing form from config: {str(e)}")
    
    def get_available_years(self):
        """Extract years from CSV files in the load folder."""
        folder_path = './siren_web/siren_files/SWIS/siren_data/'
        years = set()
        
        try:
            if os.path.exists(folder_path):
                for filename in os.listdir(folder_path):
                    if filename.lower().endswith('.csv'):
                        # Extract year from filename (assuming format like swis_load_hourly_2024_for_sam.csv)
                        parts = filename.split('_')
                        for part in parts:
                            if part.isdigit() and len(part) == 4:
                                years.add(part)
        except Exception as e:
            print(f"Error reading load folder: {e}")
        
        return sorted(years)
    
    def save_to_config(self, config_file_path):
        """
        Save the form values to the config file.
            Args:
        config_file_path (str): Path to the config file
        """
        config = configparser.ConfigParser()
        try:
            config.read(config_file_path)
        except Exception as e:
            raise Exception(f"Error reading config file: {str(e)}")
        
        # Ensure the powermatch section exists
        if 'Powermatch' not in config:
            config['Powermatch'] = {}
        
        # Map form fields to config values
        field_mappings = {
            'constraints_file': str,
            'constraints_sheet': str,
            'generators_file': str,
            'generators_sheet': str,
            'optimisation_file': str,
            'optimisation_sheet': str,
            'data_file': str,
            'results_file': str,
            'batch_file': str,
            'replace_last': str,
            'prefix_facility': str,
            'discount_rate': str,
            'carbon_price': str,
            'adjust_generators': str,
            'generator_columns': str,
        }
        
        # Update config with form values
        for field_name, conversion_func in field_mappings.items():
            if field_name in self.cleaned_data:
                value = self.cleaned_data[field_name]
                
                # Convert boolean values to 'true'/'false'
                if isinstance(value, bool):
                    value = str(value).lower()
                # Convert decimal/float values to string
                elif isinstance(value, (float, Decimal)):
                    value = str(value)
                # Convert None to empty string
                elif value is None:
                    value = ''
                if field_name == 'generator_columns':
                    try:
                        generator_data = json.loads(self.cleaned_data['generator_columns'])
                        # Save both columns to config
                        config['Powermatch']['generators_left_column'] = ','.join(generator_data['leftColumn'])
                        config['Powermatch']['generators_right_column'] = ','.join(generator_data['rightColumn'])
                    except (json.JSONDecodeError, KeyError) as e:
                        print(f"Error saving generator columns: {str(e)}")
                else:
                    config['Powermatch'][field_name] = value
        
        # Save the config file
        try:
            with open(config_file_path, 'w') as configfile:
                config.write(configfile)
        except Exception as e:
            raise Exception(f"Error saving config file: {str(e)}")
