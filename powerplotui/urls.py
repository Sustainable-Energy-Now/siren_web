# urls.py
from django.urls import path
from .views.powerplotui_home_views import PowerPlotHomeView
from .views.echart_views import eChartView
from .views import echart_views, tradingprice_views, plot3D_views

urlpatterns = [
    path('powerplotui/', PowerPlotHomeView.as_view(), name='powerplotui_home'),
    path('get-valid-choices/', PowerPlotHomeView.get_valid_choices, name='get_valid_choices'),
    path('powerplotui/echart', eChartView.as_view(), name='echarts'),
    path('get_analysis_data/', eChartView.as_view(), name='get_analysis_data'),
    path('trading_prices/', tradingprice_views.trading_price_list, name='trading_price_list'),
    path('trading_prices/update/<int:pk>/', tradingprice_views.update_trading_price, name='update_trading_price'),
    path('wem_prices/', plot3D_views.wem_price_history, name='wem_price_history'),
    path('swis_demand/', plot3D_views.swis_demand_history, name='swis_demand_history'),
]