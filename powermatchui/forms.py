# forms.py
from decimal import Decimal
from django import forms
from siren_web.models import Scenarios, Technologies, variations
from django.template.loader import render_to_string
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Div, Field, Fieldset, Submit, HTML, Button, Row, Column, ButtonHolder
from crispy_bootstrap5.bootstrap5 import Accordion
from crispy_forms.bootstrap import AccordionGroup, FormActions

class DemandYearScenario(forms.Form):
    year_choices = [(year, year) for year in Technologies.objects.values_list('year', flat=True).distinct()]
    demand_year = forms.ChoiceField(
        choices=year_choices,
        label='Select a Demand Year',
        initial='2023',
        required=True,
        widget=forms.Select(attrs={'class': 'form_input'})
        )

    scenario = forms.ModelChoiceField(
        queryset=Scenarios.objects.all().values_list('title', flat=True),
        empty_label=None,
        label='Select a Scenario',  # Add a label for the dropdown
        initial='Scen2023_Existing',
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
       # Create fields for each technology
        rows = []
        current_row = []
        for i, technology in enumerate(self.technologies):
            tech_key = f"{technology.pk}"
            field_name = f'capacity_{tech_key}'
            self.fields[field_name] = forms.DecimalField(
                label=technology.technology_name, initial=technology.capacity, required=False)
            current_row.append(
                Column(Field(field_name, css_class='form-control'), 
                css_class='form-group col-md-3 mb-0')
            )
            if (i + 1) % 4 == 0 or i == len(self.technologies) - 1:
                rows.append(Row(*current_row, css_class='form-row'))
                current_row = []

        self.helper.layout.extend([
            HTML("<hr>"),
            *rows,
            HTML("<hr>"),
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

        # Validate capacity for each technology
        for technology in self.technologies:
            tech_key = f"{technology.pk}"
            field_name = f'capacity_{tech_key}'
            capacity = cleaned_data.get(field_name)
            if capacity is None:
                self.add_error(field_name, 'This field is required.')
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

class OptimisationForm(forms.Form):
    def __init__(self, *args, **kwargs):
        self.technologies = kwargs.pop('technologies')
        self.scenario_settings = kwargs.pop('scenario_settings')
        super(OptimisationForm, self).__init__(*args, **kwargs)
        self.fields['optimise_choice'] = forms.ChoiceField(
            choices=[
                ('LCOE', 'LCOE'), 
                ('Multi', 'Multi'), 
                ('Both', 'Both')
            ], 
            label='Optimisation Choice'
        )
        self.lcoe = self.scenario_settings['optimise_lcoe'].split(',')
        self.fields['LCOE_Weight'] = forms.FloatField(label='LCOE Weight', initial=self.lcoe[0])
        self.fields['LCOE_Better']  = forms.FloatField(label='LCOE Better', initial=self.lcoe[1])
        self.fields['LCOE_Worse']  = forms.FloatField(label='LCOE Worse', initial=self.lcoe[2])
        self.load_pct  = self.scenario_settings['optimise_load_pct'].split(',')
        self.fields['Load_Weight']  = forms.FloatField(label='Load Weight', initial=self.load_pct[0])
        self.fields['Load_Better']  = forms.FloatField(label='Load Better', initial=self.load_pct[1])
        self.fields['Load_Worse']  = forms.FloatField(label='Load Worse', initial=self.load_pct[2])
        self.surplus = self.scenario_settings['optimise_surplus'].split(',')
        self.fields['Surplus_Weight']  = forms.FloatField(label='Surplus Weight', initial=self.surplus[0])
        self.fields['Surplus_Better']  = forms.FloatField(label='Surplus Better', initial=self.surplus[1])
        self.fields['Surplus_Worse']  = forms.FloatField(label='Surplus Worse', initial=self.surplus[2])
        self.re_pct  = self.scenario_settings['optimise_re_pct'].split(',')
        self.fields['RE_Weight']  = forms.FloatField(label='RE Weight', initial=self.re_pct[0])
        self.fields['RE_Better']  = forms.FloatField(label='RE Better', initial=self.re_pct[1])
        self.fields['RE_Worse']  = forms.FloatField(label='RE Worse', initial=self.re_pct[2])
        self.cost = self.scenario_settings['optimise_cost'].split(',')
        self.fields['Cost_Weight']  = forms.FloatField(label='Cost Weight', initial=self.cost[0])
        self.fields['Cost_Better']  = forms.FloatField(label='Cost Better', initial=self.cost[1])
        self.fields['Cost_Worse']  = forms.FloatField(label='Cost Worse', initial=self.cost[2])
        self.co2  = self.scenario_settings['optimise_co2'].split(',')
        self.fields['CO2_Weight']  = forms.FloatField(label='CO2 Weight', initial=self.co2[0])
        self.fields['CO2_Better']  = forms.FloatField(label='CO2 Better', initial=self.co2[1])
        self.fields['CO2_Worse']  = forms.FloatField(label='CO2 Worse', initial=self.co2[2])
        self.helper = FormHelper()
        self.helper.form_action = '/optimisation/'
        self.helper.layout = Layout(
            HTML("<hr>"),
            Div(
                Field('optimise_choice', css_class='form-control'),
                css_class='form-group'
            ),
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
            HTML("<hr>"),
            FormActions(
                Submit('submit', 'Run Optimisation',  css_class='btn btn-primary'),
            )
        )

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
