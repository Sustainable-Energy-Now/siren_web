# urls.py
from django.urls import path, include
from .views.powerplotui_home_views import PowerPlotHomeView
from .views.echart_views import eChartView
from .views import echart_views, list_spreadsheets_views, download_spreadsheet

urlpatterns = [
    path('powerplotui/', PowerPlotHomeView.as_view(), name='powerplotui_home'),
    path('powerplotui/echart', eChartView.as_view(), name='echarts'),
    path('get_analysis_data/', eChartView.as_view(), name='get_analysis_data'),
    path('spreadsheets/', list_spreadsheets_views.spreadsheet_list, name='spreadsheet_list'),
    path('download_spreadsheet/<str:spreadsheet_name>/', download_spreadsheet.download_spreadsheet, name='download_spreadsheet'),

]