# ============================================================================
# common/mixins.py
# ============================================================================
from django.shortcuts import render

class DemandScenarioSettingsMixin:
    """
    Mixin to handle demand year and scenario settings across multiple views.
    Prevents running processes until settings are explicitly applied.
    
    Usage:
        class MyView(DemandScenarioSettingsMixin):
            form_class = DemandScenarioSettings
            template_name = 'my_template.html'
    """
    form_class = None  # Must be set in the view
    template_name = None  # Must be set in the view
    
    def get_session_data(self, request):
        """Retrieve demand year and scenario from session"""
        return {
            'demand_year': request.session.get('demand_year', ''),
            'scenario': request.session.get('scenario', ''),
            'config_file': request.session.get('config_file'),
        }
    
    def handle_post(self, request):
        """Handle form submission and update session"""
        form = self.form_class(request.POST)
        success_message = ""
        
        if form.is_valid():
            demand_year = form.cleaned_data['demand_year']
            scenario = form.cleaned_data['scenario']
            
            request.session['demand_year'] = demand_year
            request.session['scenario'] = scenario
            success_message = "Settings updated."
            
            # Return a new empty form after successful save
            return self.form_class(), success_message
        
        return form, success_message
    
    def get_context_data(self, request, form=None, success_message=""):
        """Build context dictionary"""
        session_data = self.get_session_data(request)
        
        context = {
            'demand_year_scenario': form or self.form_class(),
            'demand_year': session_data['demand_year'],
            'scenario': session_data['scenario'],
            'config_file': session_data['config_file'],
            'success_message': success_message,
        }
        
        return context
    
    def dispatch_view(self, request):
        """Main dispatch method for handling GET and POST"""
        if request.method == 'POST':
            form, success_message = self.handle_post(request)
            context = self.get_context_data(request, form, success_message)
        else:
            context = self.get_context_data(request)
        
        return render(request, self.template_name, context)