# ============================================================================
# common/decorators.py
# ============================================================================
from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages

def settings_required(redirect_view='home', require_demand_year=True, require_weather_year=True):
    """
    Decorator to ensure scenario and (unless disabled) weather_year/
    demand_year are set before accessing a view. Prevents running
    processes without proper configuration.

    require_demand_year=False is for views that derive their own year at
    runtime instead of expecting the user to have picked one (see
    siren_web.database_operations.resolve_baseline_year) — e.g. the
    baseline/PowerMatch views, whose year now comes from whichever Load
    facility is actually supplying demand.

    require_weather_year=False is for views that derive their own weather
    year instead — e.g. powermapui's Run Power view, which uses the
    reference_year of the selected AEMO/ESOO demand forecast (see
    Scenarios.reference_year) when one is set, falling back to session
    weather_year only when no forecast is selected.

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
            weather_year = request.session.get('weather_year')
            demand_year = request.session.get('demand_year')
            scenario = request.session.get('scenario')

            if (not scenario
                    or (require_weather_year and not weather_year)
                    or (require_demand_year and not demand_year)):
                messages.warning(
                    request,
                    "Please set the weather year, demand year and scenario before proceeding."
                )
                return redirect(redirect_view)

            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator