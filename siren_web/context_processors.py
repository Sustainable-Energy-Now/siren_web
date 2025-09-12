# siren_web/context_processors.py
from django.conf import settings

def version(request):
    return {'APP_VERSION': settings.VERSION}