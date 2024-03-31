from django.shortcuts import render
from django.http import JsonResponse
from django.views.generic import View

# Create your views here.
from siren_web.models import Analysis, variations

class eChartView(View):
    def get(self, request):
        series_1 = request.GET.get('series_1')
        series_2 = request.GET.get('series_2')
        scenario = request.GET.get('scenario')
        variant = request.GET.get('variant')
        variation = variations.objects.filter(pk=variant)

        if not all([series_1, series_2, scenario, variant]):
            # If any of the required parameters are missing, render the template without data
            return JsonResponse({'error': 'Missing required parameters'}, status=400)

        analysis_queryset_1 = Analysis.objects.filter(
            idscenarios=scenario, 
            variation__in=[variation[0].variation_name, 'Baseline'],
            heading=series_1,
            component='Total'
            )
        
        analysis_queryset_2 = Analysis.objects.filter(
            idscenarios=scenario, 
            variation__in=[variation[0].variation_name, 'Baseline'],
            heading=series_2,
            component='Total'
            )
        
        stages = list(
            set(list(analysis_queryset_1.values_list('stage', flat=True)))
            )

        series_1_data = [0] * len(stages)
        series_2_data = [0] * len(stages)
        
        for obj in analysis_queryset_1:
            index = stages.index(obj.stage)
            series_1_data[index] = obj.quantity

        for obj in analysis_queryset_2:
            index = stages.index(obj.stage)
            series_2_data[index] = obj.quantity
            
        analysis_data = [
            {
                'stage': stage,
                series_1: value_1,
                series_2: value_2,
            }
            for stage, value_1, value_2 in zip(stages, series_1_data, series_2_data)
        ]

        return JsonResponse(analysis_data, safe=False)

  # post method
    def post(self, request, *args, **kwargs):
        # code to handle POST request
        pass