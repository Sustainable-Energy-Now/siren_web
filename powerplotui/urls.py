# urls.py
from django.urls import path, include
from .views.powerplotui_home_views import PowerPlotHomeView
from .views.echart_views import eChartView
from .views import echart_views

urlpatterns = [
    path('powerplotui/', PowerPlotHomeView.as_view(), name='powerplotui_home'),
    path('powerplotui/echart', eChartView.as_view(), name='echarts'),
    path('get_analysis_data/', eChartView.as_view(), name='get_analysis_data'),
    # Add additional URL patterns here if needed
]