# urls.py
from django.urls import path, include
from django.contrib.auth import views as auth_views
from .views import variations_views, baseline_scenario_views, \
    relate_technologies_to_scenario_views, reload_technologies_views, merit_order_views, optimisation_views, \
    powermatchui_home_views, under_construction_views
from django.views.generic import TemplateView

urlpatterns = [
    path('powermatchui/', powermatchui_home_views.powermatchui_home, name='powermatchui_home'),
    path('merit_order/', merit_order_views.set_merit_order, name='merit_order'),
    path('merit_order/save_merit_order/', merit_order_views.set_merit_order, name='save_merit_order'),
    path('reload_technologies/', reload_technologies_views.reload_technologies, name='reload_technologies'),
    path('run_baseline/', baseline_scenario_views.run_baseline, name='run_baseline'),
    path('relate_technologies/', relate_technologies_to_scenario_views.relate_technologies, name='relate_technologies'), # Maps the root URL to the main view
    path('variation/', variations_views.setup_variation, name='setup_variation'),
    path('variations/', variations_views.run_variations, name='run_variations'),
    path('baseline_scenario/', baseline_scenario_views.baseline_scenario, name='baseline_scenario'),
    # path('optimisation/', optimisation_views.run_optimisation, name='run_optimisation'),
    path('optimisation/', under_construction_views.under_construction, name='under_construction'),
    # Add additional URL patterns here if needed
]