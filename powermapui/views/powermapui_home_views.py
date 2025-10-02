from django.contrib.auth.decorators import login_required
from common.mixins import DemandScenarioSettingsMixin
from powermatchui.forms import DemandScenarioSettings

class PowermapUIHomeView(DemandScenarioSettingsMixin):
    form_class = DemandScenarioSettings
    template_name = 'powermapui_home.html'

@login_required
def powermapui_home(request):
    view = PowermapUIHomeView()
    return view.dispatch_view(request)