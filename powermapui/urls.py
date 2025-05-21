# urls.py
from django.urls import path, include
from django.contrib.auth import views as auth_views
from powermapui.views import create_scenario_views, facilities_list_views, powermapui_home_views,  \
    power_views, table_update_views, technologies_views

urlpatterns = [
    path('powermapui/', powermapui_home_views.home, name='powermapui_home'),
    path('scenarios/', create_scenario_views.create_scenario, name='display_scenarios'),
    path('scenarios/create/', create_scenario_views.update_scenario, name='update_scenario'),
    path('facilities/', facilities_list_views.facilities_list, name='facilities_list'),
    path('technologies/', technologies_views.technologies, name='technologies'),
    path('tableupdate/', table_update_views.select_table, name='table_update'),
    path('tableupdate/process/', table_update_views.update_table, name='table_update_process'),
    path('power/', power_views.generate_power, name='generate_power'),
    path('powermap/add_facility/', powermapui_home_views.add_facility, name='add_facility'),
    path('powermap/get_technologies/', powermapui_home_views.get_technologies, name='get_technologies'),
]