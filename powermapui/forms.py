# powermapui/forms.py
from django import forms
from siren_web.models import Technologies, TechnologyYears


class TechnologyForm(forms.ModelForm):
    """Form for creating and editing technologies"""

    FUEL_TYPE_CHOICES = [
        ('', '---------'),
        ('WIND', 'Wind'),
        ('SOLAR', 'Solar'),
        ('GAS', 'Gas'),
        ('COAL', 'Coal'),
        ('HYDRO', 'Hydro'),
        ('BIOMASS', 'Biomass'),
        ('OTHER', 'Other'),
    ]

    CATEGORY_CHOICES = [
        ('', '---------'),
        ('Wind', 'Wind'),
        ('Solar', 'Solar'),
        ('Storage', 'Storage'),
        ('Generator', 'Generator'),
        ('Load', 'Load'),
    ]

    class Meta:
        model = Technologies
        fields = [
            'technology_name', 'technology_signature', 'category', 'fuel_type',
            'renewable', 'dispatchable', 'lifetime', 'discount_rate',
            'emissions', 'area', 'water_usage', 'image', 'caption', 'description'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'technology_name': forms.TextInput(attrs={'size': 40}),
            'technology_signature': forms.TextInput(attrs={'size': 20, 'placeholder': 'e.g., WIND, SOLAR'}),
        }
        labels = {
            'technology_name': 'Technology Name',
            'technology_signature': 'Signature',
            'fuel_type': 'Fuel Type',
            'renewable': 'Renewable (0/1)',
            'dispatchable': 'Dispatchable (0/1)',
            'discount_rate': 'Discount Rate',
            'water_usage': 'Water Usage',
        }
        help_texts = {
            'technology_signature': 'Short unique identifier (max 20 chars)',
            'renewable': '1 = renewable, 0 = non-renewable',
            'dispatchable': '1 = dispatchable, 0 = non-dispatchable',
            'lifetime': 'Technology lifetime in years',
            'emissions': 'Emissions intensity (tCO2/MWh)',
            'area': 'Land area requirement (km2/MW)',
            'water_usage': 'Water usage (ML/MWh)',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['technology_name'].required = True
        self.fields['technology_signature'].required = True
        self.fields['category'].widget = forms.Select(choices=self.CATEGORY_CHOICES)
        self.fields['fuel_type'].widget = forms.Select(choices=self.FUEL_TYPE_CHOICES)
        for field_name, field in self.fields.items():
            if not isinstance(field.widget, forms.Select):
                field.widget.attrs['class'] = 'form-control'
            else:
                field.widget.attrs['class'] = 'form-select'


class TechnologyYearsForm(forms.ModelForm):
    """Form for creating and editing technology year data"""

    class Meta:
        model = TechnologyYears
        fields = ['idtechnologies', 'year', 'capex', 'fom', 'vom', 'fuel']
        labels = {
            'idtechnologies': 'Technology',
            'year': 'Year',
            'capex': 'CAPEX ($/kW)',
            'fom': 'Fixed O&M ($/kW/year)',
            'vom': 'Variable O&M ($/MWh)',
            'fuel': 'Fuel Cost ($/MWh)',
        }
        help_texts = {
            'capex': 'Capital expenditure in $/kW',
            'fom': 'Fixed operations & maintenance cost',
            'vom': 'Variable operations & maintenance cost',
            'fuel': 'Fuel cost per MWh generated',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['idtechnologies'].queryset = Technologies.objects.all().order_by('technology_name')
        self.fields['idtechnologies'].required = True
        self.fields['year'].required = True
        for field_name, field in self.fields.items():
            if field_name == 'idtechnologies':
                field.widget.attrs['class'] = 'form-select'
            else:
                field.widget.attrs['class'] = 'form-control'
