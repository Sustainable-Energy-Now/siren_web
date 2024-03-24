# forms.py
from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Div, Field, Submit
from crispy_forms.bootstrap import FormActions, InlineCheckboxes

class SettingsForm(forms.Form):
    new_parameter = forms.CharField(max_length=45, label='New Parameter', required=False)
    new_value = forms.CharField(max_length=300, label='New Value', required=False)

    def __init__(self, *args, **kwargs):
        self.settings = kwargs.pop('settings', [])
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Div(
                Field('new_parameter', css_class='form-control'),
                Field('new_value', css_class='form-control'),
                css_class='form-group'
            )
        )

        for setting in self.settings:
            self.fields[f'field_{setting.idsettings}'] = forms.CharField(
                max_length=300,
                label=setting.parameter,
                initial=setting.value,
                required=False
            )
            self.fields[f'delete_{setting.idsettings}'] = forms.BooleanField(
                label='Delete',
                required=False
            )
            self.helper.layout.fields.append(Div(
                Field(f'field_{setting.idsettings}', css_class='form-control'),
                Field(f'delete_{setting.idsettings}', css_class='form-control'),
                css_class='form-group'
            ))

        self.helper.layout.append(FormActions(
            Submit('submit', 'Submit', css_class='btn btn-primary')
        ))
