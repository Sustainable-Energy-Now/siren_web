from django.contrib.auth.decorators import login_required
from common.mixins import DemandScenarioSettingsMixin
from siren_web.forms import DemandScenarioSettings

class PowerplotUIHomeView(DemandScenarioSettingsMixin):
    form_class = DemandScenarioSettings
    template_name = 'powerplotui_home.html'

@login_required
def powerplotui_home(request):
    return PowerplotUIHomeView().dispatch_view(request)