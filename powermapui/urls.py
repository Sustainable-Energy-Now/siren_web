# urls.py
from django.urls import path, include
from django.contrib.auth import views as auth_views
from powermapui.views import crud_scenario_views, facilities_views, powermapui_home_views,  \
    map_views, power_views, table_update_views, technologies_views, terminals_views, wind_turbines_views
app_name = 'powermapui'

urlpatterns = [
        # Powermap home
    path('powermapui/', powermapui_home_views.powermapui_home, name='powermapui_home'),
    path('map/', map_views.home, name='map'),
    path('add_facility/', map_views.add_facility, name='add_facility'),
    path('get_facilities/', map_views.get_facilities_for_scenario, name='get_facilities_for_scenario'),
    path('get_technologies/', map_views.get_technologies, name='get_technologies'),

        # Facility-Grid Connection Management URLs
    path('facility/<int:facility_id>/manage_connections/', map_views.manage_facility_grid_connections, name='manage_facility_grid_connections'),
    path('facility/<int:facility_id>/connections/', map_views.get_facility_grid_connections, name='get_facility_grid_connections'),
    path('facility/<int:facility_id>/details/', map_views.get_facility_details, name='get_facility_details'),
    path('facility/<int:facility_id>/performance/', map_views.calculate_facility_performance, name='calculate_facility_performance'),
    
    # Grid Line Management URLs
    path('grid_line/<int:grid_line_id>/details/', map_views.get_grid_line_details, name='get_grid_line_details'),
    path('create_grid_line/', map_views.create_grid_line, name='create_grid_line'),
    path('get_grid_lines/', map_views.get_grid_lines, name='get_grid_lines'),
    path('find_nearest_grid_lines/', map_views.find_nearest_grid_lines, name='find_nearest_grid_lines'),
    
    # Loss Calculations
    path('calculate_grid_losses/', map_views.calculate_grid_losses, name='calculate_grid_losses'),
    
    # Terminal Management URLs
    path('add_terminal/', terminals_views.add_terminal, name='add_terminal'),
    path('terminal/<int:terminal_id>/details/', terminals_views.get_terminal_details, name='get_terminal_details'),
    path('get_terminals/', terminals_views.get_terminals, name='get_terminals'),
    path('find_nearest_terminals/', terminals_views.find_nearest_terminals, name='find_nearest_terminals'),
    
     # Grid Line Management with Terminal Support
    path('create_grid_line_with_terminals/', terminals_views.create_grid_line_with_terminals, name='create_grid_line_with_terminals'),
    
    # Facility Management
    path('facilities/', facilities_views.facilities_list, name='facilities_list'),
    path('facilities/create/', facilities_views.facility_create, name='facility_create'),
    path('facilities/<int:pk>/', facilities_views.facility_detail, name='facility_detail'),
    path('facilities/<int:pk>/edit/', facilities_views.facility_edit, name='facility_edit'),
    path('facilities/<int:pk>/delete/', facilities_views.facility_delete, name='facility_delete'),
    
    # Scenarios
    path('scenarios/', crud_scenario_views.display_scenario, name='display_scenarios'),
    path('scenarios/update/', crud_scenario_views.update_scenario, name='update_scenario'),
    path('scenarios/clone/', crud_scenario_views.clone_scenario, name='clone_scenario'),
    path('scenarios/edit/<int:scenario_id>/', crud_scenario_views.edit_scenario, name='edit_scenario'),
    path('scenarios/delete/<int:scenario_id>/', crud_scenario_views.delete_scenario, name='delete_scenario'),
    path('delete-scenario-ajax/<int:scenario_id>/', crud_scenario_views.delete_scenario_ajax, name='delete_scenario_ajax'),
    
    # Technology Management
    path('technologies/', technologies_views.technologies, name='technologies'),
    path('tableupdate/', table_update_views.select_table, name='table_update'),
    path('tableupdate/process/', table_update_views.update_table, name='table_update_process'),
    path('power/', power_views.generate_power, name='generate_power'),
    
        # Wind Turbines URLs
    path('wind_turbines/', wind_turbines_views.wind_turbines_list, name='wind_turbines_list'),
    path('wind_turbines/create/', wind_turbines_views.wind_turbine_create, name='wind_turbine_create'),
    path('wind_turbines/<int:pk>/', wind_turbines_views.wind_turbine_detail, name='wind_turbine_detail'),
    path('wind_turbines/<int:pk>/edit/', wind_turbines_views.wind_turbine_edit, name='wind_turbine_edit'),
    path('wind_turbines/<int:pk>/delete/', wind_turbines_views.wind_turbine_delete, name='wind_turbine_delete'),
    path('get_turbines_json/', wind_turbines_views.get_turbines_json, name='get_turbines_json'),
    
    # Facility Wind Turbine Installations URLs
    path('facility_wind_turbines/', wind_turbines_views.facility_wind_turbines_list, name='facility_wind_turbines_list'),
    path('facility_wind_turbines/create/', wind_turbines_views.facility_wind_turbine_create, name='facility_wind_turbine_create'),
    path('facility_wind_turbines/<int:pk>/edit/', wind_turbines_views.facility_wind_turbine_edit, name='facility_wind_turbine_edit'),
    path('facility_wind_turbines/<int:pk>/delete/', wind_turbines_views.facility_wind_turbine_delete, name='facility_wind_turbine_delete'),
]
