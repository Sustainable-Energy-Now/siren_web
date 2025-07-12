# urls.py
from django.urls import path, include
from django.contrib.auth import views as auth_views
from .views import exec_powermatch, variations_views, baseline_scenario_views, \
    merit_order_views, optimisation_views, \
    powermatchui_home_views, under_construction_views

urlpatterns = [
    path('powermatchui/', powermatchui_home_views.powermatchui_home, name='powermatchui_home'),
    path('merit_order/', merit_order_views.set_merit_order, name='merit_order'),
    path('baseline_scenario/', baseline_scenario_views.baseline_scenario, name='baseline_scenario'),
    path('run_baseline/', baseline_scenario_views.run_baseline, name='run_baseline'),
    path('merit_order/save_merit_order/', merit_order_views.set_merit_order, name='save_merit_order'),
    path('variation/', variations_views.setup_variation, name='setup_variation'),
    path('variations/', variations_views.run_variations, name='run_variations'),
    path('optimisation/', optimisation_views.optimisation, name='optimisation'),
    path('run_optimisation/', optimisation_views.run_optimisation, name='run_optimisation'),
    path('submit_powermatch/', exec_powermatch.submit_powermatch, name='submit_powermatch'),
    # path('optimisation/', under_construction_views.under_construction, name='under_construction'),
    # Add additional URL patterns here if needed
]