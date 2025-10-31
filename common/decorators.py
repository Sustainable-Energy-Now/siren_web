# ============================================================================
# common/decorators.py
# ============================================================================
from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages

def settings_required(redirect_view='home'):
    """
    Decorator to ensure demand_year and scenario are set before accessing a view.
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
            demand_year = request.session.get('demand_year')
            scenario = request.session.get('scenario')
            
            if not demand_year or not scenario:
                messages.warning(
                    request, 
                    "Please set the demand year and scenario before proceeding."
                )
                return redirect(redirect_view)
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator