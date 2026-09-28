# ============================================================================
# common/decorators.py
# ============================================================================
from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages

def settings_required(redirect_view='home', require_demand_year=True, require_scenario=True):
    """
    Decorator to ensure scenario and (unless disabled) demand_year are set
    before accessing a view. Prevents running processes without proper
    configuration.

    require_demand_year=False is for views that derive their own year at
    runtime instead of expecting the user to have picked one (see
    siren_web.database_operations.resolve_baseline_year) — e.g. Powermatch's
    baseline/dispatch views and powermapui's Run Power view, whose year
    comes from the selected Demand forecast's reference_year (see
    Demand.reference_year / resolve_demand_override), never from
    session['demand_year']. Powermatch views pass this False and no longer
    show or set a Demand Year anywhere.

    require_scenario=False is for views that take the Facilities scenario as
    an input of their own (e.g. Baseline Scenario's scenario selector)
    instead of reading session['scenario'].

    Usage example:
        @login_required
        @settings_required(redirect_view='powermatchui:powermatchui_home')
        def my_processing_view(request):
            # This only executes if settings are configured
            pass
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            demand_year = request.session.get('demand_year')
            scenario = request.session.get('scenario')

            missing = []
            if require_demand_year and not demand_year:
                missing.append('demand year')
            if require_scenario and not scenario:
                missing.append('scenario')

            if missing:
                joined = missing[0] if len(missing) == 1 else ', '.join(missing[:-1]) + ' and ' + missing[-1]
                messages.warning(request, f"Please set the {joined} before proceeding.")
                return redirect(redirect_view)

            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator