# forms.py
from django import forms
from siren_web.models import Scenarios, TechnologyYears, variations
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Div, Field, Submit, HTML, Row, Column
from crispy_bootstrap5.bootstrap5 import Accordion
from crispy_forms.bootstrap import AccordionGroup, FormActions

class DemandScenarioSettings(forms.Form):    
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
        self.fields['demand_year'].choices = year_choices
        
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

class CombinedVariationForm(forms.Form):
    def __init__(self, *args, **kwargs):
        DIMENSION_CHOICES = [
            ('multiplier', 'Multiplier'),
            ('capex', 'Capex'),
            ('fom', 'FOM'),
            ('vom', 'VOM'),
            ('lifetime', 'Lifetime'),
        ]
        
        scenario = kwargs.pop('scenario', None)
        technologies = kwargs.pop('technologies', {})
        selected_variation = kwargs.pop('selected_variation', None)
        variation_data = kwargs.pop('variation_data', None)
        
        super(CombinedVariationForm, self).__init__(*args, **kwargs)
        
        # Variation selection section
        if scenario:
            variations_queryset = variations.objects.filter(idscenarios=scenario)
        else:
            variations_queryset = variations.objects.none()
            
        variations_list = [variation.variation_name for variation in variations_queryset]
        variation_description_dict = {variation.variation_name: variation.variation_description for variation in variations_queryset}

        variations_choices = [(variation_name, variation_name) for variation_name in variations_list]
        variations_choices.append(('new', 'Create a new variant'))

        self.fields['variation_name'] = forms.ChoiceField(
            choices=variations_choices, 
            required=True,
            label='Select Variation',
            help_text='Choose an existing variation to edit or create a new one'
        )

        self.fields['variation_description'] = forms.CharField(
            max_length=250,
            required=False,
            widget=forms.TextInput(attrs={'readonly': True, 'placeholder': 'Description will appear here...'}),
            label='Variation Description'
        )

        # Set initial values for variation selection
        if selected_variation:
            self.fields['variation_name'].initial = selected_variation
            if selected_variation != 'Baseline' and selected_variation != 'new':
                self.fields['variation_description'].initial = variation_description_dict.get(selected_variation, '')
        else:
            # If no specific variation selected, use the first variation in the list as default
            if variations_list:
                first_variation = variations_list[0]
                self.fields['variation_name'].initial = first_variation
                self.fields['variation_description'].initial = variation_description_dict.get(first_variation, '')
            else:
                self.fields['variation_name'].initial = 'Baseline'

        # Stages field - always present but may be populated from variation_data
        if variation_data:
            self.fields['stages'] = forms.IntegerField(required=True, initial=variation_data.get('stages'))
            # Hidden field to track the original variation name for updates
            self.fields['original_variation_name'] = forms.CharField(
                required=False,
                widget=forms.HiddenInput(),
                initial=variation_data.get('variation_name'),
            )
        else:
            self.fields['stages'] = forms.IntegerField(required=True)
            self.fields['original_variation_name'] = forms.CharField(
                required=False,
                widget=forms.HiddenInput(),
            )

        # Technology accordion sections
        accordion_groups = []
        for key, value in technologies.items():
            tech_name = key
            if tech_name == 'Load':
                continue
                
            technology = value
            tech_key = f"{technology.tech_id}"
            
            # Create read-only fields for technology parameters
            self.fields[f"mult_{tech_key}"] = forms.FloatField(
                initial=technology.multiplier, 
                label="Multiplier",
                widget=forms.NumberInput(attrs={'readonly': True})
            )
            self.fields[f"capex_{tech_key}"] = forms.FloatField(
                initial=technology.capex, 
                label="Capex",
                widget=forms.NumberInput(attrs={'readonly': True})
            )
            self.fields[f"fom_{tech_key}"] = forms.FloatField(
                initial=technology.fixed_om, 
                label="FOM",
                widget=forms.NumberInput(attrs={'readonly': True})
            )
            self.fields[f"vom_{tech_key}"] = forms.FloatField(
                initial=technology.variable_om, 
                label="VOM",
                widget=forms.NumberInput(attrs={'readonly': True})
            )
            self.fields[f"lifetime_{tech_key}"] = forms.FloatField(
                initial=technology.lifetime, 
                label="Lifetime",
                widget=forms.NumberInput(attrs={'readonly': True})
            )
            
            # Step and dimension fields - populate from variation_data if available
            if variation_data and variation_data.get('variation_name') != 'new' and \
                variation_data.get('idtechnologies', {}).get('idtechnologies') == int(tech_key):
                dimension_value = variation_data.get('dimension')
                step_value = variation_data.get('step')
            else:
                dimension_value = ''
                step_value = None
                
            self.fields[f"dimension_{tech_key}"] = forms.ChoiceField(
                choices=[('', 'Select Dimension')] + DIMENSION_CHOICES,
                label="Dimension",
                required=False,
                initial=dimension_value
            )
            self.fields[f"step_{tech_key}"] = forms.FloatField(
                label="Step", 
                required=False,
                initial=step_value
            )

            # Create accordion group for this technology
            accordion_group_fields = [
                Div(
                    Field(f"mult_{tech_key}", css_class='col-md-4'),
                    Field(f"capex_{tech_key}", css_class='col-md-4'),
                    Field(f"fom_{tech_key}", css_class='col-md-4'),
                    Field(f"vom_{tech_key}", css_class='col-md-4'),
                    Field(f"lifetime_{tech_key}", css_class='col-md-4'),
                    HTML("<hr>"),
                    css_class='row'
                ),
                Div(
                    HTML('<legend>Step and Dimension</legend>'),
                    Row(
                        Field(f"step_{tech_key}", css_class='col-md-6'),
                        Field(f"dimension_{tech_key}", css_class='col-md-6'),
                    ),
                    css_class='row',
                ),
                HTML("<hr>")
            ]
            accordion_groups.append(AccordionGroup(f"{tech_name} Details", *accordion_group_fields))

        # Form layout
        self.helper = FormHelper()
        self.helper.form_action = '/variation/'
        self.helper.layout = Layout(
            # Variation selection section
            Div(
                Field('variation_name', css_class='col-md-6'),
                css_class='row', 
                id='variation_name_field'
            ),
            Div(
                Field('variation_description', css_class='col-md-8'),
                css_class='row', 
                id='variation_description_field'
            ),
            HTML("<hr>"),
            # Configuration section
            Field('stages', css_class='col-md-4'),
            Field('original_variation_name'),
            # Technology accordions
            Accordion(*accordion_groups),
            FormActions(
                Submit('submit', 'Submit'),
            )
        )
        
    def clean(self):
        cleaned_data = super().clean()
        
        # Find which technology has step and dimension values set
        selected_tech_key = None
        step_value = None
        dimension_value = None
        
        for field_name in cleaned_data.keys():
            if field_name.startswith('step_'):
                tech_key = field_name.split('_')[1]
                step_field = f"step_{tech_key}"
                dimension_field = f"dimension_{tech_key}"
                
                step_val = cleaned_data.get(step_field)
                dimension_val = cleaned_data.get(dimension_field)
                
                if step_val and dimension_val:
                    selected_tech_key = tech_key
                    step_value = step_val
                    dimension_value = dimension_val
                    break
        
        # Validate that we have the required fields for variation creation/update
        variation_name = cleaned_data.get('variation_name')
        stages = cleaned_data.get('stages')
        
        if variation_name != 'Baseline':
            if not selected_tech_key:
                raise forms.ValidationError("Please select a technology and set both step and dimension values.")
            if not stages:
                raise forms.ValidationError("Number of stages is required.")
        
        # Return processed data
        updated_data = {
            'variation_name': variation_name,
            'original_variation_name': cleaned_data.get('original_variation_name'),
            'stages': stages,
            'step': step_value,
            'dimension': dimension_value,
            'idtechnologies': selected_tech_key
        }
        
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
