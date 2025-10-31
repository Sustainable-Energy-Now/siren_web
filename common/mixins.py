# ============================================================================
# common/mixins.py
# ============================================================================
# common/mixins.py
from django.shortcuts import render

class DemandScenarioSettingsMixin:
    """
    Mixin to handle demand year and scenario settings across multiple views.
    Provides a consistent way to render and process the DemandScenarioSettings form.
    """

    form_class = None  # must be set in the view
    template_name = None  # must be set in the view
    context_form_name = 'demand_year_scenario'  # name used in templates

    def get_form(self, request, data=None):
        """Instantiate and return the form"""
        return self.form_class(data or None)

    def get_session_data(self, request):
        """Retrieve demand year and scenario from session"""
        return {
            'weather_year': request.session.get('weather_year', ''),
            'demand_year': request.session.get('demand_year', ''),
            'scenario': request.session.get('scenario', ''),
            'config_file': request.session.get('config_file'),
        }

    def handle_post(self, request):
        """Handle form submission and update session"""
        form = self.get_form(request, request.POST)
        success_message = ""

        if form.is_valid():
            data = form.cleaned_data
            request.session['weather_year'] = data['weather_year']
            request.session['demand_year'] = data['demand_year']
            request.session['scenario'] = data['scenario']
            success_message = "Settings updated."

            # return a fresh unbound form after success
            return self.get_form(request), success_message

        return form, success_message

    def get_context_data(self, request, form=None, success_message=""):
        """Assemble template context"""
        session_data = self.get_session_data(request)
        context = {
            self.context_form_name: form or self.get_form(request),
            'weather_year': session_data['weather_year'],
            'demand_year': session_data['demand_year'],
            'scenario': session_data['scenario'],
            'config_file': session_data['config_file'],
            'success_message': success_message,
        }
        return context

    def dispatch_view(self, request):
        """Main entry point"""
        if request.method == 'POST':
            form, success_message = self.handle_post(request)
            context = self.get_context_data(request, form, success_message)
        else:
            context = self.get_context_data(request)
        return render(request, self.template_name, context)
