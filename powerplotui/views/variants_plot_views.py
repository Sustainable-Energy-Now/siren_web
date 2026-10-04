from django.http import JsonResponse
from django.views.generic import View
from siren_web.models import Analysis, variations
from ..forms import parse_baseline_key


class VariantsPlotView(View):
    def get(self, request):
        """Handle AJAX GET requests for the Variants Statistics plot data"""
        try:
            series_1 = request.GET.get('series_1')
            series_2 = request.GET.get('series_2')
            series_1_component = request.GET.get('series_1_component')
            series_2_component = request.GET.get('series_2_component')
            scenario, demand = parse_baseline_key(request.GET.get('baseline'))
            variant = request.GET.get('variant')
            chart_type = request.GET.get('chart_type', 'line')
            chart_specialization = request.GET.get('chart_specialization', '')

            if not all([series_1, series_2, variant]) or scenario is None:
                return JsonResponse({'error': 'Missing required parameters'}, status=400)
            try:
                variation = variations.objects.get(pk=variant)
            except variations.DoesNotExist:
                return JsonResponse({'error': f'Variation with id {variant} not found'}, status=404)

            def series_by_stage(heading, component):
                queryset = Analysis.objects.filter(
                    idscenarios=scenario,
                    iddemandscenarios=demand,
                    variation__in=[variation.variation_name, 'Baseline'],
                    heading=heading,
                    component=component,
                ).order_by('stage')
                return {obj.stage: obj for obj in queryset}

            stages_1 = series_by_stage(series_1, series_1_component)
            stages_2 = series_by_stage(series_2, series_2_component)

            analysis_data = []
            for stage, obj_1 in stages_1.items():
                obj_2 = stages_2.get(stage)
                if obj_2 is None:
                    continue
                analysis_data.append({
                    'stage': stage,
                    'series_1_name': f'{series_1_component} {series_1}',
                    'series_1_value': obj_1.quantity,
                    'series_1_units': obj_1.units or '',
                    'series_2_name': f'{series_2_component} {series_2}',
                    'series_2_value': obj_2.quantity,
                    'series_2_units': obj_2.units or '',
                    'chart_type': chart_type,
                    'chart_specialization': chart_specialization,
                })

            return JsonResponse(analysis_data, safe=False)
        except Exception as e:
            return JsonResponse({'error': f'An error occurred: {str(e)}'}, status=500)
