from django.shortcuts import render
from django.http import JsonResponse
from django.views.generic import View
from django.core.serializers import serialize

# Create your views here.
from siren_web.models import Analysis, variations

class eChartView(View):
    def get(self, request):
        series_1 = request.GET.get('series_1')
        series_2 = request.GET.get('series_2')
        scenario = request.GET.get('scenario')
        variant = request.GET.get('variant')

        if not all([series_1, series_2, scenario, variant]):
            # If any of the required parameters are missing, render the template without data
            return JsonResponse({'error': 'Missing required parameters'}, status=400)

        variation = variations.objects.get(pk=variant)

        analysis_queryset_1 = Analysis.objects.filter(
            idscenarios=scenario,
            variation__in=[variation.variation_name, 'Baseline'],
            heading=series_1,
            component__in=['Total', 'Load Analysis']
        )

        analysis_queryset_2 = Analysis.objects.filter(
            idscenarios=scenario,
            variation__in=[variation.variation_name, 'Baseline'],
            heading=series_2,
            component__in=['Total', 'Load Analysis']
        )

        data_analysis = []

        for analysis_obj_1 in analysis_queryset_1:
            for analysis_obj_2 in analysis_queryset_2:
                if analysis_obj_1.stage == analysis_obj_2.stage:
                    data_analysis.append({
                        'stage': analysis_obj_1.stage,
                        'series_1_name': series_1,
                        'series_1_value': analysis_obj_1.quantity,
                        'series_2_name': series_2,
                        'series_2_value': analysis_obj_2.quantity
                    })

        return JsonResponse(list(data_analysis), safe=False)

    # post method
    def post(self, request, *args, **kwargs):
        # code to handle POST request
        pass