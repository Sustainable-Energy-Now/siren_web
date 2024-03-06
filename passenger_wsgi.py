import sys, os

# Add the directory containing your Django project to the Python path
sys.path.append('/siren-web/siren_web')

# Set the DJANGO_SETTINGS_MODULE environment variable
os.environ['DJANGO_SETTINGS_MODULE'] = 'siren_web.settings'

# Create a WSGI application object
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
