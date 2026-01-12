# urls.py
from django.urls import path, include
from .views import variations_views, baseline_scenario_views, demand_projection_views, \
    merit_order_views, optimisation_views, \
    powermatchui_home_views, under_construction_views, demand_factor_views
app_name = 'powermatchui'

urlpatterns = [
    path('powermatchui/', powermatchui_home_views.powermatchui_home, name='powermatchui_home'),
    path('merit_order/', merit_order_views.set_merit_order, name='merit_order'),
    path('baseline_scenario/', baseline_scenario_views.baseline_scenario, name='baseline_scenario'),
    path('run_baseline/', baseline_scenario_views.run_baseline, name='run_baseline'),
    path('run-baseline-progress/', baseline_scenario_views.run_baseline_progress, name='run_baseline_progress'),
    path('progress-stream/<str:session_id>/', baseline_scenario_views.progress_stream, name='progress_stream'),
    path('results/<str:session_id>/', baseline_scenario_views.get_results_page, name='get_results_page'),
    path('download-results/', baseline_scenario_views.download_results, name='download_results'),
    path('cancel-analysis/<str:session_id>/', baseline_scenario_views.cancel_analysis, name='cancel_analysis'),
    path('merit_order/save_merit_order/', merit_order_views.set_merit_order, name='save_merit_order'),
    path('variation/', variations_views.setup_variation, name='setup_variation'),
    path('get_variation_data/', variations_views.get_variation_data, name='get_variation_data'), 

    # path('optimisation/', optimisation_views.optimisation, name='optimisation'),
    path('run_optimisation/', optimisation_views.run_optimisation, name='run_optimisation'),
    path('optimisation/', under_construction_views.under_construction, name='under_construction'),

    # Main demand projection page
    path('demand-projection/', demand_projection_views.demand_projection_view, name='demand_projection'),

    # API endpoints for AJAX calls
    path('api/demand-projection/calculate/', demand_projection_views.calculate_demand_projection, name='calculate_demand_projection'),
    path('api/demand-projection/compare/', demand_projection_views.compare_scenarios, name='compare_scenarios'),
    path('api/demand-projection/hourly/', demand_projection_views.get_hourly_projection, name='get_hourly_projection'),
    path('api/demand-projection/update-target-scenario/', demand_projection_views.update_target_scenario_with_projection, name='update_target_scenario_with_projection'),

    # Demand Factor Type Management
    path('demand-factors/types/', demand_factor_views.factor_type_list, name='factor_type_list'),
    path('demand-factors/types/create/', demand_factor_views.factor_type_create, name='factor_type_create'),
    path('demand-factors/types/<int:pk>/edit/', demand_factor_views.factor_type_edit, name='factor_type_edit'),
    path('demand-factors/types/<int:pk>/delete/', demand_factor_views.factor_type_delete, name='factor_type_delete'),

    # Demand Factor Instance Management
    path('demand-factors/', demand_factor_views.factor_list, name='factor_list'),
    path('demand-factors/create/', demand_factor_views.factor_create, name='factor_create'),
    path('demand-factors/<int:pk>/edit/', demand_factor_views.factor_edit, name='factor_edit'),
    path('demand-factors/<int:pk>/delete/', demand_factor_views.factor_delete, name='factor_delete'),
    path('demand-factors/<int:pk>/toggle-active/', demand_factor_views.factor_toggle_active, name='factor_toggle_active'),

    # Scenario Factor Assignment
    path('demand-factors/scenario/<int:scenario_id>/assign/', demand_factor_views.scenario_factor_assignment, name='scenario_factor_assignment'),
    path('api/demand-factors/scenario/<int:scenario_id>/bulk-update/', demand_factor_views.bulk_update_scenario_factors, name='bulk_update_scenario_factors'),

    # API endpoints for factor details
    path('api/demand-factors/<int:pk>/details/', demand_factor_views.api_get_factor_details, name='api_get_factor_details'),
    path('api/demand-factors/scenario/<int:scenario_id>/summary/', demand_factor_views.api_scenario_factor_summary, name='api_scenario_factor_summary'),
]