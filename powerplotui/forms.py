# forms.py
from django import forms
from django.forms import modelformset_factory
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Row, Column, Submit, HTML
from crispy_forms.bootstrap import FormActions
from siren_web.models import Analysis, Scenarios, TradingPrice, variations

class TradingPriceForm(forms.ModelForm):
    class Meta:
        model = TradingPrice
        fields = ['trading_interval', 'reference_price']
        
class PlotForm(forms.Form):
    scenario_choices = [(scenario.idscenarios, scenario.title) for scenario in Scenarios.objects.all()]
    scenario = forms.ChoiceField(
        choices=scenario_choices,
        required=False,
        label="Choose a Scenario",
    )

    variant = forms.ChoiceField(
        choices=[],
        initial="Select a Variant",
        label="Choose a Variant"
    )

    # Start with empty choices - they'll be populated via AJAX
    series_1 = forms.ChoiceField(
        choices=[], 
        label='Select statistic for series 1',
        required=True,
        error_messages={'required': 'Please select a statistic for series 1'}
    )
    series_2 = forms.ChoiceField(
        choices=[], 
        label='Select statistic for series 2',
        required=True,
        error_messages={'required': 'Please select a statistic for series 2'}
    )

    series_1_component = forms.ChoiceField(
        choices=[], 
        label='Select component for series 1',
        required=True,
        error_messages={'required': 'Please select a component for series 1'}
    )
    series_2_component = forms.ChoiceField(
        choices=[], 
        label='Select component for series 2',
        required=True,
        error_messages={'required': 'Please select a component for series 2'}
    )

    chart_type = forms.ChoiceField(
        choices=[('line', 'Line'), ('bar', 'Bar')], label='Select chart type'
    )
    chart_specialization = forms.ChoiceField(
        choices=[
            ('', 'Select chart specialization'),
            ('Basic Line', 'Basic Line'),
            ('Stacked Line', 'Stacked Line'),
            ('Area Chart', 'Area Chart'),
            ('Smoothed Line', 'Smoothed Line'),
            ('Step Line', 'Step Line'),
            ('Basic Bar', 'Basic Bar'),
            ('Stacked Bar', 'Stacked Bar'),
        ],
        label='Select chart specialization',
        required=True,
        error_messages={'required': 'Please select a chart specialization'}
    )

    def __init__(self, *args, **kwargs):
        selected_scenario = kwargs.pop('selected_scenario', None)
        super().__init__(*args, **kwargs)

        # Determine which scenario's choices to load
        scenario_to_use = None
        if self.is_bound and self.data.get('scenario'):
            # For bound forms (POST), use the submitted scenario to recreate AJAX choices
            try:
                scenario_to_use = int(self.data.get('scenario'))
            except (ValueError, TypeError):
                scenario_to_use = None
        elif selected_scenario:
            # For initial loads with a specific scenario
            try:
                scenario_to_use = int(selected_scenario)
            except (ValueError, TypeError):
                scenario_to_use = None
        
        # Fall back to 'Current' scenario if needed
        if not scenario_to_use:
            try:
                current_scenario = Scenarios.objects.get(title='Current')
                scenario_to_use = current_scenario.idscenarios
            except Scenarios.DoesNotExist:
                scenario_to_use = None
    
        # Populate choices based on the determined scenario
        if scenario_to_use:
            variant_queryset = variations.objects.filter(idscenarios=scenario_to_use)
            self.fields['variant'].choices = [(variant.idvariations, variant.variation_name) for variant in variant_queryset]
            self.fields['scenario'].initial = scenario_to_use
            
            analysis_queryset = Analysis.objects.filter(idscenarios=scenario_to_use)
            heading_choices = [(heading, heading) for heading in analysis_queryset.values_list('heading', flat=True).distinct()]
            component_choices = [(component, component) for component in analysis_queryset.values_list('component', flat=True).distinct()]
            
            self.fields['series_1'].choices = heading_choices
            self.fields['series_2'].choices = heading_choices
            self.fields['series_1_component'].choices = component_choices
            self.fields['series_2_component'].choices = component_choices
        else:
            # No scenario available
            self.fields['variant'].choices = []

        self.helper = FormHelper()
        self.helper.form_action = '/powerplotui/'
        self.helper.layout = Layout(
            HTML("<hr>"),
            Row(
                Column('scenario', css_class='form-group col-md-3 mb-0'),
                Column('series_1_component', css_class='form-group col-md-3 mb-0'),
                Column('series_1', css_class='form-group col-md-3 mb-0'),
                Column('chart_type', css_class='form-group col-md-3 mb-0'),
                css_class='form-row'
            ),
            Row(
                Column('variant', css_class='form-group col-md-3 mb-0'),
                Column('series_2_component', css_class='form-group col-md-3 mb-0'),
                Column('series_2', css_class='form-group col-md-3 mb-0'),
                Column('chart_specialization', css_class='form-group col-md-3 mb-0'),
                css_class='form-row'
            ),
            HTML("<hr>"),
            FormActions(
                Submit('plot_type', 'Echart', formnovalidate='formnovalidate'),
                Submit('plot_type', 'Altair', formnovalidate='formnovalidate'),
                Submit('plot_type', 'Matplotlib', formnovalidate='formnovalidate'),
                Submit('export', 'Export', formnovalidate='formnovalidate'),
            )
        )
