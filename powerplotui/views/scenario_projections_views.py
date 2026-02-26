"""
Views for the SWIS 2040 Scenario Projections page.
"""
from django.shortcuts import render
from django.db.models import Sum
from siren_web.models import TargetScenario, MonthlyREPerformance
import json

SCENARIO_LABELS = {
    'base_case': 'Base Case',
    'accelerated_pipeline': 'Accelerated Pipeline',
    'delayed_pipeline': 'Delayed Pipeline',
}
SCENARIO_COLORS = {
    'base_case': '#2196F3',
    'accelerated_pipeline': '#4CAF50',
    'delayed_pipeline': '#FF9800',
}
SCENARIO_DASH = {
    'base_case': 'solid',
    'accelerated_pipeline': 'dash',
    'delayed_pipeline': 'dot',
}


def scenario_projections(request):
    """Serve the SWIS 2040 Scenario Projections report."""
    targets = TargetScenario.objects.filter(is_active=True).order_by('scenario_type', 'year')

    scenario_data = {}
    for t in targets:
        st = t.scenario_type
        if st not in scenario_data:
            scenario_data[st] = []

        underlying = t.underlying_demand or 1.0
        wind = t.wind_generation or 0
        solar = t.solar_generation or 0
        dpv = t.dpv_generation or 0
        biomass = t.biomass_generation or 0
        re_pct = t.target_re_percentage

        # Compute stacked area % proportionally so they sum to re_pct
        total_known = wind + solar + dpv + biomass
        if total_known > 0:
            wind_pct = re_pct * wind / total_known
            solar_pct = re_pct * solar / total_known
            dpv_pct = re_pct * dpv / total_known
            biomass_pct = re_pct * biomass / total_known
            storage_pct = max(0.0, re_pct - wind_pct - solar_pct - dpv_pct - biomass_pct)
        else:
            wind_pct = solar_pct = dpv_pct = biomass_pct = storage_pct = 0.0

        scenario_data[st].append({
            'year': t.year,
            're_pct': round(re_pct, 1),
            'wind_gwh': round(wind, 0),
            'solar_gwh': round(solar, 0),
            'dpv_gwh': round(dpv, 0),
            'biomass_gwh': round(biomass, 0),
            'gas_gwh': round(t.gas_generation or 0, 0),
            'storage_mwh': round(t.storage or 0, 0),
            'operational_demand': round(t.operational_demand or 0, 0),
            'underlying_demand': round(underlying, 0),
            'emissions_kt': round((t.target_emissions_tonnes or 0) / 1000, 1),
            'probability': round(t.probability_percentage or 0, 0),
            'target_type': t.target_type,
            'wind_pct': round(wind_pct, 2),
            'solar_pct': round(solar_pct, 2),
            'dpv_pct': round(dpv_pct, 2),
            'biomass_pct': round(biomass_pct, 2),
            'storage_pct': round(storage_pct, 2),
        })

    # Annual historical RE% from MonthlyREPerformance
    try:
        historical_qs = MonthlyREPerformance.objects.values('year').annotate(
            op_demand=Sum('operational_demand'),
            und_demand=Sum('underlying_demand'),
            wind=Sum('wind_generation'),
            solar=Sum('solar_generation'),
            dpv=Sum('dpv_generation'),
            biomass=Sum('biomass_generation'),
            hydro_dis=Sum('hydro_discharge'),
            storage_dis=Sum('storage_discharge'),
            emissions=Sum('total_emissions_tonnes'),
        ).order_by('year')

        historical_data = []
        for h in historical_qs:
            und = h['und_demand'] or 1.0
            re_sources = (
                (h['wind'] or 0) + (h['solar'] or 0) + (h['dpv'] or 0) +
                (h['biomass'] or 0) + (h['hydro_dis'] or 0) + (h['storage_dis'] or 0)
            )
            re_pct = min(100.0, re_sources / und * 100)
            historical_data.append({
                'year': h['year'],
                're_pct': round(re_pct, 1),
                'operational_demand': round(h['op_demand'] or 0, 0),
                'underlying_demand': round(und, 0),
                'emissions_kt': round((h['emissions'] or 0) / 1000, 1),
            })
    except Exception:
        historical_data = []

    has_data = bool(scenario_data)

    # Latest actual RE% for metric card
    current_re_pct = None
    current_year = None
    if historical_data:
        latest = historical_data[-1]
        current_re_pct = latest['re_pct']
        current_year = latest['year']

    # Base case 2030 and 2040 for metric cards
    base_2040 = None
    base_2030 = None
    if 'base_case' in scenario_data:
        for d in scenario_data['base_case']:
            if d['year'] == 2040:
                base_2040 = d
            if d['year'] == 2030:
                base_2030 = d

    annual_review_year = current_year or 2024

    context = {
        'scenario_data_json': json.dumps(scenario_data),
        'historical_data_json': json.dumps(historical_data),
        'scenario_labels_json': json.dumps(SCENARIO_LABELS),
        'scenario_colors_json': json.dumps(SCENARIO_COLORS),
        'scenario_dash_json': json.dumps(SCENARIO_DASH),
        'has_data': has_data,
        'current_re_pct': current_re_pct,
        'current_year': current_year,
        'base_2040': base_2040,
        'base_2030': base_2030,
        'annual_review_year': annual_review_year,
    }
    return render(request, 'ret_dashboard/scenario_projections.html', context)
