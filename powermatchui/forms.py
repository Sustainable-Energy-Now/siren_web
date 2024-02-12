# forms.py
from django import forms

class LoadYearForm(forms.Form):
    load_year = forms.ChoiceField(choices=[('2021', '2021'), ('2022', '2022')], initial='2022')

    LEVEL_OF_DETAIL_CHOICES = [
        ('Summary', 'Summary'),
        ('Detailed', 'Detailed'),
    ]
    level_of_detail = forms.ChoiceField(choices=LEVEL_OF_DETAIL_CHOICES, initial='Summary', widget=forms.RadioSelect)