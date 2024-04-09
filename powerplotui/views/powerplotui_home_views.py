from django.views.generic import TemplateView
from django.shortcuts import render
from siren_web.models import Analysis, Scenarios, variations
from ..forms import PlotForm

class PowerPlotHomeView(TemplateView):
    template_name = 'powerplotui_home.html'

    # Function to fetch data from the database
    def get_analysis_data(self, analysis_queryset):
        analysis_data = []
        for obj in analysis_queryset:
            obj_data = {}
            for field in obj._meta.fields:
                if field.name == 'idanalysis':
                    continue
                value = getattr(obj, field.name)
                if field.name == 'idscenarios':
                    obj_data['Scenario'] = value.title
                else:
                    obj_data[field.name.capitalize()] = value
            analysis_data.append(obj_data)
        return analysis_data
        
    def get(self, request):
        analysis_queryset = Analysis.objects.all()[:5]
        analysis_data = self.get_analysis_data(analysis_queryset)
            
        plotform = PlotForm()
        context = {
            'analysis_data' : analysis_data,
            'plotform': plotform,
        }
        return render(request, 'powerplotui_home.html', context)

    def post(self, request):
        plotform = PlotForm(request.POST)
        idscenarios = request.POST.get('scenario')
        idvariant  = request.POST.get('variant')
        variant  = variations.objects.filter(pk=idvariant)
        if 'filter' in request.POST:
            # Filter the Analysis data based on the selected scenario and variant
            analysis_queryset = \
                Analysis.objects.filter(
                    idscenarios_id=idscenarios, 
                    variation__in=[variant[0].variation_name, 'Baseline']
                    )[:6]
            analysis_data = self.get_analysis_data(analysis_queryset)
            context = {
                'plotform': plotform,
                'analysis_data': analysis_data,
            }
        elif 'echart' in request.POST:
            # analysis_queryset = \
            #     Analysis.objects.filter(
            #         idscenarios_id=idscenarios, 
            #         variation__in=[variant[0].variation_name, 'Baseline']
            #         )
            # analysis_data = self.get_analysis_data(analysis_queryset)
            # Get the selected values from the request.GET
            series_1 = request.POST.get('series_1')
            series_2 = request.POST.get('series_2')
            plot_type = 'echarts'  # or any other plot_type value
            chart_type = request.POST.get('chart_type')

        # Prepare the context with the selected values
            context = {
                'series_1': series_1,
                'series_2': series_2,
                'scenario': idscenarios,
                'variant': idvariant,
                'chart_type': chart_type,
            }
            # Render the appropriate template based on the selected plot_type
            if plot_type == 'echarts':
                return render(request, 'echarts.html', context)
            elif plot_type == 'matplotlib':
                return render(request, 'matplotlib.html', context)
            elif plot_type == 'altair':
                return render(request, 'altair.html', context)

        return render(request, 'powerplotui_home.html', context)