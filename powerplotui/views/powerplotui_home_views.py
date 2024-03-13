from django.views.generic import TemplateView
from django.shortcuts import render
from siren_web.models import Analysis

class PowerPlotHomeView(TemplateView):
    template_name = 'powerplotui_home.html'

    # Function to fetch data from the database
    def get(self, request):
        analysis_queryset = Analysis.objects.all()[:5]
        analysis_data = []
        for obj in analysis_queryset:
            obj_data = {}
            for field in obj._meta.fields:
                value = getattr(obj, field.name)
                obj_data[field.name] = value
            analysis_data.append(obj_data)
            
        headings = Analysis.objects.values_list('heading', flat=True).distinct()
        context = {
            'analysis_data' : analysis_data,
            'headings': headings,
        }
        return render(request, 'powerplotui_home.html', context)

    def post(self, request):
        # Get the selected values from the request.GET
        x_column = request.POST.get('x_column')
        y_column = request.POST.get('y_column')
        plot_type = request.POST.get('plot_type')
        chart_type = request.POST.get('chart_type')
        headings = Analysis.objects.values_list('heading', flat=True).distinct()

        # Prepare the context with the selected values
        context = {
            'headings': headings,
            'x_column': x_column,
            'y_column': y_column,
            'chart_type': chart_type,
        }
        # Render the appropriate template based on the selected plot_type
        if plot_type == 'echarts':
            return render(request, 'echarts.html', context)
        elif plot_type == 'matplotlib':
            return render(request, 'matplotlib.html', context)
        elif plot_type == 'altair':
            return render(request, 'altair.html', context)
        else:
            # Handle invalid plot_type value
            return render(request, 'powerplotui_home.html', context)