from django.apps import AppConfig

class PowermapuiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "powermapui"

    def ready(self):
        import powermapui.signals # Import the signals module