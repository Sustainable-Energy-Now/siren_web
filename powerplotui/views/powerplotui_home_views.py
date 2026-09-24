from django.contrib.auth.decorators import login_required
from common.mixins import DemandScenarioSettingsMixin
from siren_web.forms import WeatherScenarioSettings

class PowerplotUIHomeView(DemandScenarioSettingsMixin):
    form_class = WeatherScenarioSettings
    template_name = 'powerplotui_home.html'

@login_required
def powerplotui_home(request):
    return PowerplotUIHomeView().dispatch_view(request)