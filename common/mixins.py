# ============================================================================
# common/mixins.py
# ============================================================================
# common/mixins.py
from django.shortcuts import render
from siren_web.models import Demand, ReportComment, Scenarios

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
            # Some forms (PowerMatchScenarioSettings) don't have a
            # demand_year field at all -- their year is derived at run
            # time instead (see resolve_baseline_year), not user-picked.
            if 'demand_year' in data:
                request.session['demand_year'] = data['demand_year']
            request.session['scenario'] = data['scenario']
            success_message = "Settings updated."

            # return a fresh unbound form after success
            return self.get_form(request), success_message

        return form, success_message

    def get_context_data(self, request, form=None, success_message=""):
        """Assemble template context"""
        session_data = self.get_session_data(request)

        # Facilities Take-up (Scenarios.forecast_year) vs. Demand Forecast/
        # Load Factor (DemandScenarios.forecast_year) -- informational only,
        # since "any combination" is allowed; see settings_form_partial.html.
        scenario_forecast_year = None
        if session_data['scenario']:
            scenario_obj = Scenarios.objects.filter(title=session_data['scenario']).first()
            if scenario_obj is not None:
                scenario_forecast_year = scenario_obj.forecast_year

        demand_forecast_year = None
        demand_id = request.session.get('demand_scenario_demand_id')
        if demand_id:
            demand_obj = Demand.objects.filter(pk=demand_id).select_related('demand_scenario').first()
            if demand_obj is not None and hasattr(demand_obj, 'demand_scenario'):
                demand_forecast_year = demand_obj.demand_scenario.forecast_year

        context = {
            self.context_form_name: form or self.get_form(request),
            'weather_year': session_data['weather_year'],
            'demand_year': session_data['demand_year'],
            'scenario': session_data['scenario'],
            'config_file': session_data['config_file'],
            'success_message': success_message,
            'scenario_forecast_year': scenario_forecast_year,
            'demand_forecast_year': demand_forecast_year,
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

class CommentsMixin:
    """
    Mixin to add comments functionality to RET dashboard views.
    
    Usage in your existing views:
    
    For function-based views, use the helper function:
        context = get_comments_context('monthly', year, month=month)
        # Add to your existing context
    
    For class-based views, inherit from this mixin.
    """
    
    def get_comments_context(self, report_type, year, month=None, quarter=None):
        """
        Get the comments context for a report.
        
        Args:
            report_type: 'monthly', 'quarterly', or 'annual'
            year: The year
            month: The month (for monthly reports)
            quarter: The quarter (for quarterly reports)
        
        Returns:
            dict with 'comments' and 'report_type' keys
        """
        comments = ReportComment.get_comments_for_report(
            report_type, year, month=month, quarter=quarter
        )
        
        return {
            'comments': comments,
            'report_type': report_type,
        }

def get_comments_context(report_type, year, month=None, quarter=None):
    """
    Helper function to get comments context for function-based views.
    
    Usage in your ret_dashboard_views.py:
    
        from ..mixins import get_comments_context
        
        def ret_dashboard(request, year=None, month=None):
            # ... existing code ...
            
            # Add comments
            comments_ctx = get_comments_context('monthly', year, month=month)
            context.update(comments_ctx)
            
            return render(request, 'ret_dashboard/dashboard.html', context)
    """
    comments = ReportComment.get_comments_for_report(
        report_type, year, month=month, quarter=quarter
    )
    
    return {
        'comments': comments,
        'report_type': report_type,
    }