# urls.py
from django.urls import path, include
from django.contrib.auth import views as auth_views
from powermapui.views import crud_scenario_views, facilities_views, powermapui_home_views,  \
    power_views, table_update_views, technologies_views
app_name = 'powermapui'

urlpatterns = [
    path('powermapui/', powermapui_home_views.home, name='powermapui_home'),
    path('powermapui/add_facility/', powermapui_home_views.add_facility, name='add_facility'),
    path('powermapui/get_technologies/', powermapui_home_views.get_technologies, name='get_technologies'),
    path('powermapui/get_facilities/', powermapui_home_views.get_facilities_for_scenario, name='get_facilities_for_scenario'),
    path('powermapui/get_grid_lines/', powermapui_home_views.get_grid_lines, name='get_grid_lines'),
    path('powermapui/find_nearest_grid_lines/', powermapui_home_views.find_nearest_grid_lines, name='find_nearest_grid_lines'),
    path('powermapui/create_grid_line/', powermapui_home_views.create_grid_line, name='create_grid_line'),
    path('facility/<int:facility_id>/grid_connections/', powermapui_home_views.get_facility_grid_connections, name='get_facility_grid_connections'),
    path('powermapui/calculate_grid_losses/', powermapui_home_views.calculate_grid_losses, name='calculate_grid_losses'),
    path('scenarios/', crud_scenario_views.display_scenario, name='display_scenarios'),
    path('scenarios/update/', crud_scenario_views.update_scenario, name='update_scenario'),
    path('scenarios/clone/', crud_scenario_views.clone_scenario, name='clone_scenario'),
    path('scenarios/edit/<int:scenario_id>/', crud_scenario_views.edit_scenario, name='edit_scenario'),
    path('scenarios/delete/<int:scenario_id>/', crud_scenario_views.delete_scenario, name='delete_scenario'),
    path('delete-scenario-ajax/<int:scenario_id>/', crud_scenario_views.delete_scenario_ajax, name='delete_scenario_ajax'),
    path('facilities/', facilities_views.facilities_list, name='facilities_list'),
    path('technologies/', technologies_views.technologies, name='technologies'),
    path('tableupdate/', table_update_views.select_table, name='table_update'),
    path('tableupdate/process/', table_update_views.update_table, name='table_update_process'),
    path('power/', power_views.generate_power, name='generate_power'),
]