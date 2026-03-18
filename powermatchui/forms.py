# forms.py
from django import forms
from siren_web.models import Scenarios, TechnologyYears, variations
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Div, Field, Submit, HTML, Row, Column
from crispy_bootstrap5.bootstrap5 import Accordion
from crispy_forms.bootstrap import AccordionGroup, FormActions

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
