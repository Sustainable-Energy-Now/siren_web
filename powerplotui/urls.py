# urls.py
from django.urls import path
from .views.variants_views import VariantsView
from .views.echart_views import eChartView
from .views import tradingprice_views, plot3D_views, powerplotui_home_views, supplyfactors_views, scada_views

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
    
    # Scada-related URLs
    path('scada_analysis/', scada_views.scada_analysis_report, name='scada_analysis'),
    path('scada_analysis/<int:year>/<int:month>/', scada_views.scada_analysis_report, name='scada_analysis_detail'),
    
    # Miscellaneous URLs
    path('trading_prices/', tradingprice_views.trading_price_list, name='trading_price_list'),
    path('trading_prices/update/<int:pk>/', tradingprice_views.update_trading_price, name='update_trading_price'),
    path('wem_prices/', plot3D_views.wem_price_history, name='wem_price_history'),
    path('swis_demand/', plot3D_views.swis_demand_history, name='swis_demand_history'),
]