# ============================================================================
# common/decorators.py
# ============================================================================
from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages

def settings_required(redirect_view='home'):
    """
    Decorator to ensure weather_year, demand_year and scenario are set before accessing a view.
    Prevents running processes without proper configuration.
    
    Usage example:
        @login_required
        @settings_required(redirect_view='powermatchui_home')
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
            
            if not weather_year or not demand_year or not scenario:
                messages.warning(
                    request, 
                    "Please set the weather year, demand year and scenario before proceeding."
                )
                return redirect(redirect_view)
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator