import altair as alt
import base64
from django.views.generic import TemplateView
from django.shortcuts import render, redirect
import io
from siren_web.models import Analysis, Scenarios, variations
from ..forms import PlotForm
import matplotlib
matplotlib.use('Agg')  # Use the 'Agg' backend for non-interactive plotting
import matplotlib.pyplot as plt
import logging
from ..views.altair_views import AltairChartView
from ..views.matplotlib_views import MatplotlibChartView
import pandas as pd

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
    
    def create_chart(self, request, plot_type):
        series_1 = request.POST.get('series_1')
        series_2 = request.POST.get('series_2')
        scenario = request.POST.get('scenario')
        variant = request.POST.get('variant')
        chart_type = request.POST.get('chart_type', 'line')
        chart_specialization = request.POST.get('chart_specialization', '')
        variation = variations.objects.get(pk=variant)

        analysis_queryset_1 = Analysis.objects.filter(
            idscenarios=scenario,
            variation__in=[variation.variation_name, 'Baseline'],
            heading=series_1,
            component__in=['Total', 'Load Analysis']
        ).order_by('stage')

        analysis_queryset_2 = Analysis.objects.filter(
            idscenarios=scenario,
            variation__in=[variation.variation_name, 'Baseline'],
            heading=series_2,
            component__in=['Total', 'Load Analysis']
        ).order_by('stage')
        
        analysis_data = []
        
        # Create a dictionary from analysis_queryset_2 with stage as the key
        stage_dict = {obj.stage: obj for obj in analysis_queryset_2}

        for analysis_obj_1 in analysis_queryset_1:
            # Check if the stage exists in the dictionary
            if analysis_obj_1.stage in stage_dict:
                analysis_obj_2 = stage_dict[analysis_obj_1.stage]
                analysis_data.append({
                    'stage': analysis_obj_1.stage,
                    'series_1_name': series_1,
                    'series_1_value': analysis_obj_1.quantity,
                    'series_2_name': series_2,
                    'series_2_value': analysis_obj_2.quantity,
                    'chart_type': chart_type,
                    'chart_specialization': chart_specialization
                })
        if (plot_type == 'Altair'):
            # Create an Altair chart
            df = pd.DataFrame([{'stage': item['stage'], 'series_1_name': item['series_1_name'], 'series_1_value': item['series_1_value']} for item in analysis_data])
            series_1_name = analysis_data[0]['series_1_name']

            chart = alt.Chart(df).mark_line().encode(
                x='stage',
                y=alt.Y('series_1_value', title=df['series_1_name'].iloc[0]),
                color='series_1_name'
            )

            # Save the chart as an HTML string
            html = chart.to_html()

            context = {
                'chart_html': html,
            }
            return render(request, 'altair.html', context)
        else:
            # Set the logging level to WARNING to suppress DEBUG and INFO messages
            logging.getLogger('matplotlib').setLevel(logging.WARNING)
            # Create a Matplotlib figure and plot the data
            fig, ax = plt.subplots()
            ax.plot([item['stage']for item in analysis_data], [item['series_1_value'] for item in analysis_data])
            ax.plot([item['stage']for item in analysis_data], [item['series_2_value'] for item in analysis_data])
            ax.set_xlabel(analysis_data[0]['series_1_name'])
            ax.set_ylabel(analysis_data[0]['series_2_name'])
            ax.set_title('Analysis Plot')

            # Save the figure to a BytesIO object
            buf = io.BytesIO()
            fig.savefig(buf, format='png')
            buf.seek(0)

            # Encode the image data as a base64 string
            image_data = base64.b64encode(buf.getvalue()).decode('utf-8')

            context = {
                'image_data': image_data,
                # ... (other context variables)
            }

            return render(request, 'matplotlib.html', context)
        
    def get(self, request):
        analysis_queryset = Analysis.objects.all()[:6]
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
        plot_type = request.POST.get('plot_type', '')
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
        elif plot_type:
            # Get the selected values from the request.GET
            series_1 = request.POST.get('series_1')
            series_2 = request.POST.get('series_2')
            chart_type = request.POST.get('chart_type')
            chart_specialization = request.POST.get('chart_specialization')

        # Prepare the context with the selected values
            context = {
                'series_1': series_1,
                'series_2': series_2,
                'scenario': idscenarios,
                'variant': idvariant,
                'chart_type': chart_type,
                'chart_specialization': chart_specialization,
            }
            # Render the appropriate template based on the selected plot_type
            if plot_type in ['Altair', 'Matplotlib']:
                return self.create_chart(request, plot_type)
            elif plot_type == 'Echart':
                return render(request, 'echarts.html', context)

        # return render(request, 'powerplotui_home.html', context)