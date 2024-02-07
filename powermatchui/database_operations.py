# In powermatchui database operations

from .models import Settings

def fetch_settings_data():
    try:
        settings_queryset = Settings.objects.order_by('context')
        settings_list = list(settings_queryset.values())
        settings = {setting['context']: setting for setting in settings_list}
        return settings
    except Exception as e:
        print(f"Error fetching settings data: {e}")
        return None
