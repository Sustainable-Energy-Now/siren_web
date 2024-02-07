from django import forms

class LoadYearForm(forms.Form):
    load_year = forms.ChoiceField(choices=[('2021', '2021'), ('2022', '2022')], initial='2022')
