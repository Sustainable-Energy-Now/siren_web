from django.contrib.auth.decorators import login_required
from common.mixins import DemandScenarioSettingsMixin
from siren_web.forms import DemandScenarioSettings

class PowermatchUIHomeView(DemandScenarioSettingsMixin):
    form_class = DemandScenarioSettings
    template_name = 'powermatchui_home.html'

@login_required
def powermatchui_home(request):
    return PowermatchUIHomeView().dispatch_view(request)