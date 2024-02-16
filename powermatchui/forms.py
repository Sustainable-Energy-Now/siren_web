# forms.py
from django import forms
from .models import Scenarios, Technologies

class LoadYearForm(forms.Form):
    load_year = forms.ChoiceField(choices=[('2021', '2021'), ('2022', '2022')], initial='2022')

    LEVEL_OF_DETAIL_CHOICES = [
        ('Summary', 'Summary'),
        ('Detailed', 'Detailed'),
    ]
    level_of_detail = forms.ChoiceField(choices=LEVEL_OF_DETAIL_CHOICES, initial='Summary', widget=forms.RadioSelect)
    
class BatchForm(forms.Form):
    scenario = forms.ModelChoiceField(queryset=Scenarios.objects.all(), empty_label=None)

class MeritOrderForm(forms.Form):
    merit_order = forms.ModelMultipleChoiceField(queryset=Technologies.objects.none(), widget=forms.SelectMultiple(attrs={'class': 'sortable'}))
    excluded_resources = forms.ModelMultipleChoiceField(queryset=Technologies.objects.none(), widget=forms.SelectMultiple(attrs={'class': 'sortable'}))
