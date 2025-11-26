# urls.py
from django.urls import path
from .views.variants_views import VariantsView
from .views.echart_views import eChartView
from .views import facility_scada_views, tradingprice_views, plot3D_views, powerplotui_home_views, ret_dashboard_views, \
    ret_targets_views, supplyfactors_views, scada_views

urlpatterns = [
    path('powerplotui/', powerplotui_home_views.powerplotui_home, name='powerplotui_home'),
    
    # Supply factor-related URLs
    path('supply_plot/', supplyfactors_views.supply_plot_view, name='supply_plot'),
    path('get_supply_data/', supplyfactors_views.get_supply_data, name='get_supply_data'),
    path('get_comparison_data/', supplyfactors_views.get_comparison_data, name='get_comparison_data'),
    path('supply_plot_view/', supplyfactors_views.supply_plot_view, name='supply_plot_view'),
    path('get_facility_years/', supplyfactors_views.get_facility_years, name='get_facility_years'),
    path('get_technology_data/', supplyfactors_views.get_technology_data, name='get_technology_data'),
    path('get_technology_comparison_data/', supplyfactors_views.get_technology_comparison_data, name='get_technology_comparison_data'),  # Fixed the missing comma and added name for
 
    # Variant-related URLs
    path('variants/', VariantsView.as_view(), name='variants'),
    path('get_valid_choices/', VariantsView.get_valid_choices, name='get_valid_choices'),
    path('powerplotui/echart', eChartView.as_view(), name='echarts'),
    path('get_analysis_data/', eChartView.as_view(), name='get_analysis_data'),

    # Main SCADA plot view
    path('scada-plot/', facility_scada_views.scada_plot_view, name='scada_plot'),
    
    # API endpoints for SCADA data
    path('get_scada_data/', facility_scada_views.get_scada_data, name='get_scada_data'),
    path('get_scada_comparison/', facility_scada_views.get_scada_comparison_data, name='get_scada_comparison'),
    path('get_scada_technology/', facility_scada_views.get_scada_technology_data, name='get_scada_technology'),
    path('get_scada_technology_comparison/', facility_scada_views.get_scada_technology_comparison_data, name='get_scada_technology_comparison'),
    
    # Scada-related URLs
    path('scada_analysis/', scada_views.scada_analysis_report, name='scada_analysis'),
    path('scada_analysis/<int:year>/<int:month>/', scada_views.scada_analysis_report, name='scada_analysis_detail'),
    # Export historical data endpoint
    path('scada_analysis/export/', scada_views.export_historical_data, name='export_historical_data'),

    # RET Dashboard URLs
    path('ret_dashboard/', ret_dashboard_views.ret_dashboard, name='ret_dashboard'),
    path('ret_dashboard/<int:year>/<int:month>/', ret_dashboard_views.ret_dashboard, name='ret_dashboard_period'),
    path('ret_quarterly_report/<int:year>/<int:quarter>/', ret_dashboard_views.quarterly_report, name='quarterly_report'),
    path('ret_annual_review/<int:year>/', ret_dashboard_views.annual_review, name='annual_review'),
    
    # API endpoints for data updates
    path('api/ret_dashboard/update_monthly/', ret_dashboard_views.update_monthly_data, name='update_monthly_data'),
    path('api/ret_dashboard/calculate/<int:year>/<int:month>/', ret_dashboard_views.api_calculate_monthly, name='api_calculate_monthly'),

    # Main targets list view
    path('ret_dashboard/targets/', ret_targets_views.ret_targets_list, name='ret_targets_list'),
    
    # Target CRUD operations
    path('ret_dashboard/targets/create/', ret_targets_views.ret_target_create, name='ret_target_create'),
    path('ret_dashboard/targets/<int:target_id>/update/', ret_targets_views.ret_target_update, name='ret_target_update'),
    path('ret_dashboard/targets/<int:target_id>/delete/', ret_targets_views.ret_target_delete, name='ret_target_delete'),
    
    # Scenario CRUD operations
    path('ret_dashboard/scenarios/create/', ret_targets_views.scenario_create, name='scenario_create'),
    path('ret_dashboard/scenarios/<int:scenario_id>/update/', ret_targets_views.scenario_update, name='scenario_update'),
    path('ret_dashboard/scenarios/<int:scenario_id>/delete/', ret_targets_views.scenario_delete, name='scenario_delete'),
    path('ret_dashboard/scenarios/<int:scenario_id>/toggle/', ret_targets_views.scenario_toggle_active, name='scenario_toggle_active'),
    
    # =========================================================================
    # API Endpoints (JSON responses)
    # =========================================================================
    path('api/ret_dashboard/targets/', ret_targets_views.api_targets_list, name='api_targets_list'),
    path('api/ret_dashboard/targets/<int:target_id>/', ret_targets_views.api_target_detail, name='api_target_detail'),
    path('api/ret_dashboard/scenarios/', ret_targets_views.api_scenarios_list, name='api_scenarios_list'),
    path('api/ret_dashboard/scenarios/<int:scenario_id>/', ret_targets_views.api_scenario_detail, name='api_scenario_detail'),

    # Miscellaneous URLs
    path('trading_prices/', tradingprice_views.trading_price_list, name='trading_price_list'),
    path('trading_prices/update/<int:pk>/', tradingprice_views.update_trading_price, name='update_trading_price'),
    path('wem_prices/', plot3D_views.wem_price_history, name='wem_price_history'),
    path('swis_demand/', plot3D_views.swis_demand_history, name='swis_demand_history'),
]