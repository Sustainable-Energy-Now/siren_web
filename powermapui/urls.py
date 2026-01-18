from django.urls import path
from powermapui.views import crud_scenario_views, facilities_views, facility_solar_views, \
    facility_storage_views, crud_terminals_views, gridlines_views, powermapui_home_views, \
    map_views, power_views, storage_views, table_update_views, \
    technologies_views, terminals_connections_views, terminals_dashboard, terminals_views, \
    wind_turbines_views
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

    # Facility-specific installation creation URLs
    path('facilities/<int:facility_id>/solar/create/', facility_solar_views.facility_solar_create, name='facility_solar_create_for_facility'),
    path('facilities/<int:facility_id>/storage/create/', facility_storage_views.facility_storage_create, name='facility_storage_create_for_facility'),
    path('facilities/<int:facility_id>/wind/create/', wind_turbines_views.facility_wind_turbine_create, name='facility_wind_turbine_create'),

    # Basic Terminal CRUD
    path('terminals/', crud_terminals_views.terminals_list, name='terminals_list'),
    path('terminals/create/', crud_terminals_views.terminal_create, name='terminal_create'),
    path('terminals/<int:pk>/', crud_terminals_views.terminal_detail, name='terminal_detail'),
    path('terminals/<int:pk>/edit/', crud_terminals_views.terminal_edit, name='terminal_edit'),
    path('terminals/<int:pk>/delete/', crud_terminals_views.terminal_delete, name='terminal_delete'),
    
    # Terminal Connection Management
    path('terminals/<int:pk>/connections/', terminals_connections_views.terminal_connections, name='terminal_connections'),
    path('terminals/<int:pk>/add-gridline/', terminals_connections_views.terminal_add_gridline, name='terminal_add_gridline'),
    path('terminals/<int:pk>/remove-gridline/<int:gridline_id>/', terminals_connections_views.terminal_remove_gridline, name='terminal_remove_gridline'),
    path('gridlines/<int:pk>/', gridlines_views.gridline_detail, name='gridline_detail'),

    # ========== TERMINAL DASHBOARD ==========
    path('terminals/dashboard/', terminals_dashboard.terminals_dashboard, name='terminals_dashboard'),
    path('terminals/health-check/', terminals_dashboard.terminal_health_check, name='terminal_health_check'),

    # ========== GRID LINES CRUD (NEW) ==========
    path('gridlines/', gridlines_views.gridlines_list, name='gridlines_list'),
    path('gridlines/create/', gridlines_views.gridline_create, name='gridline_create'),
    path('gridlines/<int:pk>/', gridlines_views.gridline_detail, name='gridline_detail'),
    path('gridlines/<int:pk>/edit/', gridlines_views.gridline_edit, name='gridline_edit'),
    path('gridlines/<int:pk>/delete/', gridlines_views.gridline_delete, name='gridline_delete'),
    
        # Terminal Views
    path('terminals/<int:pk>/facilities/', terminals_connections_views.terminal_facilities_view, name='terminal_facilities'),
    path('terminals/<int:pk>/gridlines/', terminals_connections_views.terminal_gridlines_view, name='terminal_gridlines'),
    path('terminals/<int:pk>/network/', terminals_connections_views.terminal_node_diagram, name='terminal_node_diagram'),
    
    # Facility Connection
    path('terminals/<int:terminal_pk>/connect-facility/<int:facility_pk>/', 
         terminals_connections_views.connect_facility_to_terminal, 
         name='connect_facility_to_terminal'),
    path('terminals/<int:pk>/remove-facility/<int:gridline_id>/', terminals_connections_views.terminal_remove_facility, name='terminal_remove_facility'),

    
    # Scenarios
    path('scenarios/', crud_scenario_views.display_scenario, name='display_scenarios'),
    path('scenarios/update/', crud_scenario_views.update_scenario, name='update_scenario'),
    path('scenarios/clone/', crud_scenario_views.clone_scenario, name='clone_scenario'),
    path('scenarios/edit/<int:scenario_id>/', crud_scenario_views.edit_scenario, name='edit_scenario'),
    path('scenarios/delete/<int:scenario_id>/', crud_scenario_views.delete_scenario, name='delete_scenario'),
    path('delete-scenario-ajax/<int:scenario_id>/', crud_scenario_views.delete_scenario_ajax, name='delete_scenario_ajax'),
    
    # Technology Management (Original read-only view)
    path('technologies/', technologies_views.technologies, name='technologies'),
    # Technologies CRUD
    path('technologies/list/', technologies_views.technology_list, name='technology_list'),
    path('technologies/create/', technologies_views.technology_create, name='technology_create'),
    path('technologies/<int:pk>/', technologies_views.technology_detail, name='technology_detail'),
    path('technologies/<int:pk>/edit/', technologies_views.technology_edit, name='technology_edit'),
    path('technologies/<int:pk>/delete/', technologies_views.technology_delete, name='technology_delete'),
    path('technologies/api/search/', technologies_views.technology_search_api, name='technology_search_api'),
    # TechnologyYears CRUD
    path('technology-years/create/', technologies_views.technology_years_create, name='technology_years_create'),
    path('technologies/<int:technology_pk>/years/create/', technologies_views.technology_years_create, name='technology_years_create_for_tech'),
    path('technology-years/<int:pk>/edit/', technologies_views.technology_years_edit, name='technology_years_edit'),
    path('technology-years/<int:pk>/delete/', technologies_views.technology_years_delete, name='technology_years_delete'),
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
    
    # Power curve management URLs
    path('wind-turbines/<int:turbine_pk>/power-curves/create/', wind_turbines_views.power_curve_create, name='power_curve_create'),
    path('power-curves/<int:pk>/edit/', wind_turbines_views.power_curve_edit, name='power_curve_edit'),
    path('power-curves/<int:pk>/delete/', wind_turbines_views.power_curve_delete, name='power_curve_delete'),
    path('power-curves/<int:pk>/toggle-active/', wind_turbines_views.power_curve_toggle_active, name='power_curve_toggle_active'),
    path('power-curves/<int:pk>/data-json/', wind_turbines_views.power_curve_data_json, name='power_curve_data_json'),
    
    # Facility Wind Turbine Installations URLs
    path('facility_wind_turbines/create/', wind_turbines_views.facility_wind_turbine_create, name='facility_wind_turbine_create'),
    path('facility_wind_turbines/<int:pk>/edit/', wind_turbines_views.facility_wind_turbine_edit, name='facility_wind_turbine_edit'),
    path('facility_wind_turbines/<int:pk>/delete/', wind_turbines_views.facility_wind_turbine_delete, name='facility_wind_turbine_delete'),
    
        # Storage Technologies (new)
    path('storage/', storage_views.storage_list, name='storage_list'),
    path('storage/create/', storage_views.storage_create, name='storage_create'),
    path('storage/<int:pk>/', storage_views.storage_detail, name='storage_detail'),
    path('storage/<int:pk>/edit/', storage_views.storage_edit, name='storage_edit'),
    path('api/storage/', storage_views.get_storage_json, name='get_storage_json'),

    # Facility Solar Installations (installation-specific capacity)
    path('facility-solar/<int:pk>/', facility_solar_views.facility_solar_detail, name='facility_solar_detail'),
    path('facility-solar/<int:pk>/edit/', facility_solar_views.facility_solar_edit, name='facility_solar_edit'),
    path('facility-solar/<int:pk>/delete/', facility_solar_views.facility_solar_delete, name='facility_solar_delete'),
    path('api/facility-solar/', facility_solar_views.get_facility_solar_json, name='get_facility_solar_json'),

    # Facility Storage Installations (installation-specific capacity)
    path('facility-storage/<int:pk>/', facility_storage_views.facility_storage_detail, name='facility_storage_detail'),
    path('facility-storage/<int:pk>/edit/', facility_storage_views.facility_storage_edit, name='facility_storage_edit'),
    path('facility-storage/<int:pk>/delete/', facility_storage_views.facility_storage_delete, name='facility_storage_delete'),
    path('api/facility-storage/', facility_storage_views.get_facility_storage_json, name='get_facility_storage_json'),

]
