# urls.py
from django.urls import path, include
from django.contrib.auth import views as auth_views
from .views import batch_views, generate_facilities_views, merit_order_views, optimisation_views, powermatchui_home_views, under_construction_views
from django.views.generic import TemplateView

urlpatterns = [
    path('powermatchui/', powermatchui_home_views.powermatchui_home, name='powermatchui_home'),
    path('run_powermatch/', powermatchui_home_views.run_powermatch, name='run_powermatch'),
    path('generate_facilities/', generate_facilities_views.generate_facilities, name='generate_facilities'), # Maps the root URL to the main view
    path('batch/', batch_views.setup_batch, name='setup_batch'),
    path('save_order/', merit_order_views.set_merit_order, name='merit_order'),
    path('merit_order/', merit_order_views.set_merit_order, name='merit_order'),
    path('merit_order/save_order/', merit_order_views.set_merit_order, name='save_merit_order'),
    # path('optimisation/', optimisation_views.run_optimisation, name='run_optimisation'),
    path('optimisation/', under_construction_views.under_construction, name='under_construction'),
    # Add additional URL patterns here if needed
]