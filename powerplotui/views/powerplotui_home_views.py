from django.contrib.auth.decorators import login_required
from common.mixins import DemandScenarioSettingsMixin
from powermatchui.forms import DemandScenarioSettings

class PowerplotUIHomeView(DemandScenarioSettingsMixin):
    form_class = DemandScenarioSettings
    template_name = 'powerplotui_home.html'

@login_required
def powerplotui_home(request):
    view = PowerplotUIHomeView()
    return view.dispatch_view(request)