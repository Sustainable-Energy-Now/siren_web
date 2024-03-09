# urls.py
from django.urls import path, include
from django.contrib.auth import views as auth_views
from .views import batch_views, create_scenario_views, facilities_list_views, home_views, merit_order_views, optimisation_views,  \
    siren_system_views, table_update_views, technologies_detail_views, technologies_list_views, under_construction_views
from django.views.generic import TemplateView

urlpatterns = [
    path('', home_views.home, name='home'),  # Maps the root URL to the main view
    path('run_powermatch/', home_views.run_powermatch, name='run_powermatch'),  # Maps the root URL to the main view
    path('save_order/', merit_order_views.set_merit_order, name='merit_order'),
    path('scenarios/', create_scenario_views.create_scenario, name='display_scenarios'),
    path('scenarios/create/', create_scenario_views.update_scenario, name='update_scenario'),
    path('facilities/', facilities_list_views.facilities_list, name='facilities_list'),
    path('merit_order/', merit_order_views.set_merit_order, name='merit_order'),
    path('merit_order/save_order/', merit_order_views.set_merit_order, name='save_merit_order'),
    path('batch/', batch_views.setup_batch, name='setup_batch'),
    # path('optimisation/', optimisation_views.run_optimisation, name='run_optimisation'),
    path('optimisation/', under_construction_views.under_construction, name='under_construction'),
    path('siren_system/', siren_system_views.siren_system_view, name='siren_system_view'),
    path('technologies/', technologies_list_views.display_technologies, name='display_technologies'),
    path('technologies_detail/', technologies_detail_views.technologies_detail, name='technologies_detail'),
    path('tableupdate/', table_update_views.select_table, name='table_update'),
    path('tableupdate/process/', table_update_views.update_table, name='table_update_process'),
    # Add additional URL patterns here if needed
]