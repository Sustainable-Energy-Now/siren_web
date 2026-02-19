from django.contrib.auth.decorators import login_required
from common.decorators import settings_required
from django.shortcuts import render
from siren_web.forms import DemandScenarioSettings
from siren_web.database_operations import fetch_module_settings_data, fetch_scenario_settings_data
from siren_web.models import facilities, Technologies, Terminals, Scenarios, GridLines
import json


@login_required
@settings_required(redirect_view='powermapui:powermapui_home')
def pipeline_map(request):
    """Pipeline map view showing facilities with status, probability, and capacity encoding."""
    weather_year = request.session.get('weather_year', '')
    demand_year = request.session.get('demand_year', '')
    scenario = request.session.get('scenario', '')
    config_file = request.session.get('config_file')
    success_message = ''

    if request.method == 'POST':
        demand_weather_scenario = DemandScenarioSettings(request.POST)
        if demand_weather_scenario.is_valid():
            demand_year = demand_weather_scenario.cleaned_data['demand_year']
            request.session['demand_year'] = demand_year
            scenario = demand_weather_scenario.cleaned_data['scenario']
            request.session['scenario'] = scenario
            success_message = "Settings updated."

    demand_weather_scenario = DemandScenarioSettings(initial={
        'demand_year': demand_year,
        'scenario': scenario
    })

    # Build pipeline facilities data
    pipeline_facilities = []
    categories = set()
    year_min = None
    year_max = None
    summary_stats = {}

    if scenario:
        try:
            scenario_obj = Scenarios.objects.get(title=scenario)
            facilities_qs = facilities.objects.filter(
                scenarios=scenario_obj,
                latitude__isnull=False,
                longitude__isnull=False
            ).select_related('idtechnologies')

            for f in facilities_qs:
                retirement_year = None
                if f.commissioning_date and f.idtechnologies and f.idtechnologies.lifetime:
                    retirement_year = f.commissioning_date.year + int(f.idtechnologies.lifetime)

                category = f.idtechnologies.category if f.idtechnologies and hasattr(f.idtechnologies, 'category') else 'Unknown'
                categories.add(category)

                probability = f.commissioning_probability if f.commissioning_probability is not None else 1.0
                status = f.status if f.status else 'commissioned'
                capacity = float(f.capacity) if f.capacity else 0

                # Track year range
                if f.commissioning_date:
                    cy = f.commissioning_date.year
                    if year_min is None or cy < year_min:
                        year_min = cy
                    if year_max is None or cy > year_max:
                        year_max = cy
                if retirement_year:
                    if year_max is None or retirement_year > year_max:
                        year_max = retirement_year

                # Summary stats
                if status not in summary_stats:
                    summary_stats[status] = {'count': 0, 'total_mw': 0}
                summary_stats[status]['count'] += 1
                summary_stats[status]['total_mw'] += capacity

                pipeline_facilities.append({
                    'idfacilities': f.idfacilities,
                    'facility_name': f.facility_name,
                    'latitude': f.latitude,
                    'longitude': f.longitude,
                    'capacity': capacity,
                    'status': status,
                    'commissioning_probability': probability,
                    'commissioning_date': f.commissioning_date.isoformat() if f.commissioning_date else None,
                    'decommissioning_date': f.decommissioning_date.isoformat() if f.decommissioning_date else None,
                    'technology_name': f.idtechnologies.technology_name if f.idtechnologies else 'Unknown',
                    'technology_category': category,
                    'technology_lifetime': float(f.idtechnologies.lifetime) if f.idtechnologies and f.idtechnologies.lifetime else None,
                    'retirement_year': retirement_year,
                })
        except Scenarios.DoesNotExist:
            pass

    # Grid lines data
    grid_lines_data = []
    for gl in GridLines.objects.filter(active=True):
        grid_lines_data.append({
            'idgridlines': gl.idgridlines,
            'line_name': gl.line_name,
            'line_type': gl.line_type,
            'voltage_level': gl.voltage_level,
            'coordinates': gl.get_line_coordinates(),
            'from_latitude': gl.from_latitude,
            'from_longitude': gl.from_longitude,
            'to_latitude': gl.to_latitude,
            'to_longitude': gl.to_longitude,
        })

    # Terminals data
    terminals_data = []
    for t in Terminals.objects.filter(active=True):
        terminals_data.append({
            'idterminals': t.idterminals,
            'terminal_name': t.terminal_name,
            'terminal_type': t.terminal_type,
            'primary_voltage_kv': t.primary_voltage_kv,
            'latitude': t.latitude,
            'longitude': t.longitude,
        })

    if year_min is None:
        year_min = 2020
    if year_max is None:
        year_max = 2050

    context = {
        'demand_weather_scenario': demand_weather_scenario,
        'weather_year': weather_year,
        'demand_year': demand_year,
        'scenario': scenario,
        'config_file': config_file,
        'success_message': success_message,
        'pipeline_facilities_json': json.dumps(pipeline_facilities),
        'grid_lines_json': json.dumps(grid_lines_data),
        'terminals_json': json.dumps(terminals_data),
        'categories': json.dumps(sorted(categories)),
        'summary_stats_json': json.dumps(summary_stats),
        'year_min': year_min,
        'year_max': year_max,
    }
    return render(request, 'pipeline_map.html', context)
