# views.py
from django.shortcuts import render, redirect, get_object_or_404
from siren_web.models import Settings
from siren_web.forms import SettingsForm

def settings_view(request, sw_context):
    success_message = ""
    settings = Settings.objects.filter(sw_context=sw_context)
    if request.method == 'POST':
        form = SettingsForm(request.POST, settings=settings)
        if form.is_valid():
            new_parameter = form.cleaned_data.get('new_parameter')
            new_value = form.cleaned_data.get('new_value')
            if new_parameter and new_value:
                new_setting = Settings.objects.create(
                    sw_context=sw_context,
                    parameter=new_parameter,
                    value=new_value
                )

            for setting in settings:
                field_name = f'field_{setting.idsettings}'
                new_value = form.cleaned_data.get(field_name)
                delete_setting = request.POST.get(f'delete_{setting.idsettings}')
                if delete_setting:
                    setting.delete()
                elif new_value != setting.value:
                    setting.value = new_value
                    setting.save()
            success_message = f"{sw_context} setting have been updated."
            return redirect('settings', sw_context=sw_context)
    else:
        form = SettingsForm(settings=settings)

    context = {
        'form': form,
        'settings': settings,
        'sw_context': sw_context,
        'success_message': success_message,
    }
    return render(request, 'settings.html', context)