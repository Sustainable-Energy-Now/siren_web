# forms.py
from django import forms
from django.forms import modelformset_factory
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Row, Column, Submit, HTML
from crispy_forms.bootstrap import FormActions
from siren_web.models import Analysis, variations, ReportComment
from siren_web.database_operations import list_baselines


def parse_baseline_key(key):
    """'<scenario_id>:<demand_scenario_id>' -> (int, int), or (None, None) if malformed."""
    try:
        scenario_id, demand_id = str(key).split(':')
        return int(scenario_id), int(demand_id)
    except (TypeError, ValueError):
        return None, None


def baseline_variations(scenario_id, demand_id):
    """Variations of the scenario that have Analysis rows for this baseline's demand scenario."""
    names = Analysis.objects.filter(
        idscenarios=scenario_id, iddemandscenarios=demand_id,
    ).exclude(variation='Baseline').values_list('variation', flat=True).distinct()
    return variations.objects.filter(idscenarios=scenario_id, variation_name__in=list(names))


class PlotForm(forms.Form):
    baseline = forms.ChoiceField(
        choices=[],
        required=False,
        label="Choose a Baseline",
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
        selected_baseline = kwargs.pop('selected_baseline', None)
        form_data = kwargs.pop('form_data', None)
        super().__init__(*args, **kwargs)

        # Populated here, not in the class body: a class-body query runs at
        # import time (e.g. during `manage.py check`), before the table is
        # guaranteed to exist.
        self.fields['baseline'].choices = (
            [('', 'Select a Baseline')] + [(b['key'], b['label']) for b in list_baselines()]
        )

        # For unbound forms, just show basic choices from the baseline
        if selected_baseline:
            self.set_basic_choices(selected_baseline, variation_name=None)
        else:
            # No baseline available
            self.fields['variant'].choices = []
        # For bound forms (POST) with form_data returned from a charting module selected values
        if form_data:
            self.set_initial_values(form_data)
            
        self.helper = FormHelper()
        self.helper.form_action = '/variants/'
        self.helper.layout = Layout(
            HTML("<hr>"),
            Row(
                Column('baseline', css_class='form-group col-md-3 mb-0'),
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
                Submit('plot_type', 'Plot', formnovalidate='formnovalidate'),
                Submit('export', 'Export', formnovalidate='formnovalidate'),
            )
        )

    def set_initial_values(self, form_data):
        # Restore previously selected choices
        self.fields['baseline'].initial = form_data['baseline']
        self.fields['variant'].initial = form_data['variant']
        self.fields['series_1_component'].initial = form_data['series_1_component']
        self.fields['series_1'].initial = form_data['series_1']
        self.fields['series_2_component'].initial = form_data['series_2_component']
        self.fields['series_2'].initial = form_data['series_2']
        self.fields['chart_type'].initial = form_data['chart_type']
        self.fields['chart_specialization'].initial = form_data['chart_specialization']

    def set_basic_choices(self, baseline_key, variation_name=None):
        """Set basic choices when constraints don't apply"""
        scenario_id, demand_id = parse_baseline_key(baseline_key)
        if scenario_id is None:
            self.fields['variant'].choices = []
            return
        analysis_filter = {'idscenarios': scenario_id, 'iddemandscenarios': demand_id}
        if variation_name:
            analysis_filter['variation'] = variation_name

        analysis_queryset = Analysis.objects.filter(**analysis_filter)
        variant_queryset = baseline_variations(scenario_id, demand_id)
        self.fields['variant'].choices = [(variant.idvariations, variant.variation_name) for variant in variant_queryset]
        heading_choices = [(heading, heading) for heading in analysis_queryset.values_list('heading', flat=True).distinct()]
        self.fields['series_1'].choices = heading_choices
        self.fields['series_2'].choices = heading_choices
        component_choices = [(component, component) for component in analysis_queryset.values_list('component', flat=True).distinct()]
        self.fields['series_1_component'].choices = component_choices
        self.fields['series_2_component'].choices = component_choices
        
class ReportCommentForm(forms.ModelForm):
    """Form for adding comments to reports."""
    
    class Meta:
        model = ReportComment
        fields = ['content', 'category']
        widgets = {
            'content': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Add a comment...',
                'class': 'comment-textarea',
            }),
            'category': forms.Select(attrs={
                'class': 'comment-category-select',
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].required = False

class CommentEditForm(forms.ModelForm):
    """Form for editing existing comments."""
    
    class Meta:
        model = ReportComment
        fields = ['content', 'category', 'is_pinned', 'is_resolved']
        widgets = {
            'content': forms.Textarea(attrs={
                'rows': 3,
                'class': 'comment-textarea',
            }),
        }