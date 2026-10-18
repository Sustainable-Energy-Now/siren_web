"""Access helpers for the Grid Map: modeller-only updates and iframe embedding."""
from functools import wraps

from django.http import JsonResponse

MODELLERS_GROUP = 'modellers'


def is_modeller(user):
    """True if the user may make updates (member of the 'modellers' group)."""
    return user.is_authenticated and user.groups.filter(name=MODELLERS_GROUP).exists()


def modellers_required(view_func):
    """Restrict a JSON endpoint to modellers; returns 401/403 JSON otherwise."""
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Login required'}, status=401)
        if not is_modeller(request.user):
            return JsonResponse({'error': 'Only modellers can make updates'}, status=403)
        return view_func(request, *args, **kwargs)
    return _wrapped


def is_embedded(request):
    """True when the page is being loaded inside an iframe (or ?embed=1 is given)."""
    return request.GET.get('embed') == '1' or request.headers.get('Sec-Fetch-Dest') == 'iframe'
