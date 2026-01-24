# urls.py
from django.urls import path
from .views.variants_views import VariantsView
from .views.echart_views import eChartView
from .views import facility_scada_views, plot3D_views, powerplotui_home_views, ret_dashboard_views, \
    ret_comments_views, ret_targets_views, ret_pdf_views, supplyfactors_views, scada_views, \
    generation_comparison_views, risk_analysis_views

urlpatterns = [
    path('powerplotui/', powerplotui_home_views.powerplotui_home, name='powerplotui_home'),
    
    # Supply factor-related URLs
    path('supply_plot/', supplyfactors_views.supply_plot_view, name='supply_plot'),
    path('get_supply_data/', supplyfactors_views.get_supply_data, name='get_supply_data'),
    path('get_comparison_data/', supplyfactors_views.get_comparison_data, name='get_comparison_data'),
    path('get_facility_years/', supplyfactors_views.get_facility_years, name='get_facility_years'),
    path('get_technology_data/', supplyfactors_views.get_technology_data, name='get_technology_data'),
    path('get_technology_comparison_data/', supplyfactors_views.get_technology_comparison_data, name='get_technology_comparison_data'),
    path('export_supply_to_excel/', supplyfactors_views.export_supply_to_excel, name='export_supply_to_excel'),
 
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
    path('export_scada_to_excel/', facility_scada_views.export_scada_to_excel, name='export_scada_to_excel'),
    
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
    path('ret_dashboard/comments/add/', ret_comments_views.add_comment, name='ret_comment_add'),
    path('ret_dashboard/comments/<int:comment_id>/edit/', ret_comments_views.edit_comment, name='ret_comment_edit'),
    path('ret_dashboard/comments/<int:comment_id>/delete/', ret_comments_views.delete_comment, name='ret_comment_delete'),
    path('ret_dashboard/comments/<int:comment_id>/toggle-pin/', ret_comments_views.toggle_pin_comment, name='ret_comment_toggle_pin'),
    path('ret_dashboard/comments/<int:comment_id>/toggle-resolve/', ret_comments_views.toggle_resolve_comment, name='ret_comment_toggle_resolve'),
    path('ret_executive_summary/update/', ret_dashboard_views.update_executive_summary, name='ret_executive_summary_update'),

    # PDF Publishing URLs
    path('ret_quarterly_report/<int:year>/<int:quarter>/publish/', ret_pdf_views.publish_quarterly_report, name='publish_quarterly_report'),
    path('ret_annual_review/<int:year>/publish/', ret_pdf_views.publish_annual_report, name='publish_annual_report'),
    path('published_reports/', ret_pdf_views.published_reports_list, name='published_reports_list'),
    path('published_reports/<int:report_id>/view/', ret_pdf_views.view_published_report, name='view_published_report'),
    path('published_reports/<int:report_id>/download/', ret_pdf_views.download_published_report, name='download_published_report'),
    path('published_reports/<int:report_id>/view_html/', ret_pdf_views.view_published_html, name='view_published_html'),

    # Main targets list view
    path('ret_dashboard/targets/', ret_targets_views.ret_targets_list, name='ret_targets_list'),

    # Unified Target/Scenario CRUD operations
    path('ret_dashboard/scenarios/create/', ret_targets_views.scenario_create, name='scenario_create'),
    path('ret_dashboard/scenarios/<int:scenario_id>/update/', ret_targets_views.scenario_update, name='scenario_update'),
    path('ret_dashboard/scenarios/<int:scenario_id>/delete/', ret_targets_views.scenario_delete, name='scenario_delete'),
    path('ret_dashboard/scenarios/<int:scenario_id>/toggle/', ret_targets_views.scenario_toggle_active, name='scenario_toggle_active'),

    # =========================================================================
    # API Endpoints (JSON responses)
    # =========================================================================
    path('api/ret_dashboard/scenarios/', ret_targets_views.api_scenarios_list, name='api_scenarios_list'),
    path('api/ret_dashboard/scenarios/<int:scenario_id>/', ret_targets_views.api_scenario_detail, name='api_scenario_detail'),

    # SCADA vs SupplyFactors Comparison URLs
    path('generation-comparison/', generation_comparison_views.generation_comparison_view, name='generation_comparison'),
    path('get_facility_scada_vs_supply/', generation_comparison_views.get_facility_scada_vs_supply, name='scada_vs_supply_facility'),
    path('get_facility_group_scada_vs_supply/', generation_comparison_views.get_facility_group_scada_vs_supply, name='scada_vs_supply_facility_group'),
    path('get_technology_scada_vs_supply/', generation_comparison_views.get_technology_scada_vs_supply, name='scada_vs_supply_technology'),
    path('get_technology_group_scada_vs_supply/', generation_comparison_views.get_technology_group_scada_vs_supply, name='scada_vs_supply_technology_group'),
    path('export_generation_comparison_to_excel/', generation_comparison_views.export_generation_comparison_to_excel, name='export_generation_comparison_to_excel'),

    # Miscellaneous URLs
    path('wem_prices/', plot3D_views.wem_price_history, name='wem_price_history'),
    path('swis_demand/', plot3D_views.swis_demand_history, name='swis_demand_history'),

    # ==========================================================================
    # SWIS Risk Analysis URLs
    # Note: Scenarios are managed via powermapui - this uses existing scenarios
    # ==========================================================================
    path('risk/', risk_analysis_views.risk_dashboard, name='risk_dashboard'),
    path('risk/scenarios/', risk_analysis_views.scenario_list, name='risk_scenario_list'),
    path('risk/scenarios/<int:scenario_id>/', risk_analysis_views.risk_scenario_detail, name='risk_scenario_detail'),
    path('risk/scenarios/<int:scenario_id>/events/add/', risk_analysis_views.risk_event_create, name='risk_event_create'),
    path('risk/compare/', risk_analysis_views.risk_comparison_view, name='risk_comparison'),

    # Risk Event URLs
    path('risk/events/<int:event_id>/update/', risk_analysis_views.risk_event_update, name='risk_event_update'),
    path('risk/events/<int:event_id>/delete/', risk_analysis_views.risk_event_delete, name='risk_event_delete'),

    # Risk Analysis API Endpoints
    path('api/risk/scenarios/<int:scenario_id>/matrix/', risk_analysis_views.api_risk_matrix_data, name='api_risk_matrix'),
    path('api/risk/comparison/', risk_analysis_views.api_scenario_comparison_data, name='api_risk_comparison'),
    path('api/risk/summary/', risk_analysis_views.api_risk_summary, name='api_risk_summary'),
    path('api/risk/scenarios/<int:scenario_id>/profile/', risk_analysis_views.api_category_risk_profile, name='api_risk_profile'),
    path('api/risk/scenarios/<int:scenario_id>/', risk_analysis_views.api_scenario_detail, name='api_risk_scenario_detail'),
]