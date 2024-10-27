# forms.py
from django import forms
from django.forms import modelformset_factory
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Div, Field, Submit, Fieldset, Row, Column, Submit, HTML
from crispy_forms.bootstrap import FormActions, InlineCheckboxes
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

    variant_choices = [(variant.idvariations, variant.variation_name) for variant in variations.objects.all()]
    variant = forms.ChoiceField(
        choices=[],
        initial="Select a Variant",
        label="Choose a Variant"
    )

    heading_choices = [(heading, heading) for heading in Analysis.objects.values_list('heading', flat=True).distinct()]
    series_1 = forms.ChoiceField(choices=heading_choices, label='Select statistic for series 1')
    series_2 = forms.ChoiceField(choices=heading_choices, label='Select statistic for series 2')

    component_choices = [(component, component) for component in Analysis.objects.values_list('component', flat=True).distinct()]
    series_1_component = forms.ChoiceField(choices=component_choices, label='Select component for series 1')
    series_2_component = forms.ChoiceField(choices=component_choices, label='Select component for series 2')

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
        required=False,
    )

    def __init__(self, *args, **kwargs):
        selected_scenario = kwargs.pop('selected_scenario', None)
        super().__init__(*args, **kwargs)

        if selected_scenario:
            variant_queryset = variations.objects.filter(idscenarios=selected_scenario)
            self.fields['variant'].choices = [(variant.idvariations, variant.variation_name) for variant in variant_queryset]
            self.fields['scenario'].initial = selected_scenario
        else:
            self.fields['variant'].choices = self.variant_choices
            self.fields['scenario'].initial = "Select a Scenario"

        self.helper = FormHelper()
        self.helper.form_action = '/powerplotui/'
        self.helper.layout = Layout(
            HTML("<hr>"),
            Row(
                Column('scenario', css_class='form-group col-md-3 mb-0'),
                Column('series_1', css_class='form-group col-md-3 mb-0'),
                Column('series_1_component', css_class='form-group col-md-3 mb-0'),
                Column('chart_type', css_class='form-group col-md-3 mb-0'),
                css_class='form-row'
            ),
            Row(
                Column('variant', css_class='form-group col-md-3 mb-0'),
                Column('series_2', css_class='form-group col-md-3 mb-0'),
                Column('series_2_component', css_class='form-group col-md-3 mb-0'),
                Column('chart_specialization', css_class='form-group col-md-3 mb-0'),
                css_class='form-row'
            ),
            HTML("<hr>"),
            FormActions(
                Submit('filter', 'Filter', formnovalidate='formnovalidate'),
                Submit('plot_type', 'Echart', formnovalidate='formnovalidate'),
                Submit('plot_type', 'Altair', formnovalidate='formnovalidate'),
                Submit('plot_type', 'Matplotlib', formnovalidate='formnovalidate'),
                Submit('export', 'Export', formnovalidate='formnovalidate'),
            )
        )
