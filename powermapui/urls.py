# urls.py
from django.urls import path, include
from django.contrib.auth import views as auth_views
from powermapui.views import create_scenario_views, facilities_list_views, powermapui_home_views,  \
    table_update_views, technologies_detail_views, technologies_list_views
from django.views.generic import TemplateView

urlpatterns = [
    path('powermapui/', powermapui_home_views.home, name='powermapui_home'),
    path('scenarios/', create_scenario_views.create_scenario, name='display_scenarios'),
    path('scenarios/create/', create_scenario_views.update_scenario, name='update_scenario'),
    path('facilities/', facilities_list_views.facilities_list, name='facilities_list'),
    path('technologies/', technologies_list_views.display_technologies, name='display_technologies'),
    path('technologies_detail/', technologies_detail_views.technologies_detail, name='technologies_detail'),
    path('tableupdate/', table_update_views.select_table, name='table_update'),
    path('tableupdate/process/', table_update_views.update_table, name='table_update_process'),
    # Add additional URL patterns here if needed
]