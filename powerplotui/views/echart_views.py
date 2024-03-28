from django.shortcuts import render
from django.http import JsonResponse
from django.views.generic import TemplateView

# Create your views here.
from siren_web.models import Analysis

class eChartView(TemplateView):
    template_name = 'echarts.html'

    def get(self, request):
        # code to handle GET request
        # Get the selected heading, component, and variation combinations from the request
        x_column = ''
        y_column = ''
        data = {}
        if 'x_column' in request.GET and 'y_column' in request.GET:
            # Query the Analysis model to get the data
            x_column = request.GET.get('x_column')
            y_column = request.GET.get('y_column')
            analysis_data1 = Analysis.objects.filter(heading=x_column, component='Total').values('stage', 'quantity')
            analysis_data2 = Analysis.objects.filter(heading=y_column, component='Total').values('stage', 'quantity')

        # Prepare the data for the Echarts plot
            data = {
                'x_axis': list(set([data['stage'] for data in analysis_data1] + [data['stage'] for data in analysis_data2])),
                'series1': [{'name': f'{x_column}', 'data': [data['quantity'] for data in analysis_data1]}],
                'series2': [{'name': f'{y_column}', 'data': [data['quantity'] for data in analysis_data2]}]
            }
            # data = {
            #     'x_axis': ['Jan', 'Feb', 'Mar'], 
            #     'series1': [{'name': 'Capacity', 'data': [30000, 50000, 40000]}],
            #     'series2': [{'name': 'LCOE', 'data': [20000, 30000, 35000]}]
            #     }

            return JsonResponse(data)
        context = {
           'x_column': x_column,
            'y_column': y_column,
            'chart_data': data
            }
        return render(request, 'echarts.html', context)

  # post method
    def post(self, request, *args, **kwargs):
        # code to handle POST request
        pass