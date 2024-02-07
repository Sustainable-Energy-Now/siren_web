from django.urls import path
from . import views

urlpatterns = [
    path('', views.main, name='main'),  # Maps the root URL to the main view
    # Add additional URL patterns here if needed
]
