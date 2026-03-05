from django.contrib.auth.decorators import login_required
from common.decorators import settings_required
from django.shortcuts import render
from siren_web.forms import DemandScenarioSettings
from siren_web.models import (
    facilities, Terminals, Scenarios, GridLines,
    CELStage, FacilityCELAlignment,
)
from powermapui.utils.cel_viability_service import CELViabilityService
import json


@login_required
@settings_required(redirect_view='powermapui:powermapui_home')
def cel_map(request):
    """
    CEL transmission map.

    Facilities are coloured either by development status
    or by CEL viability tier — toggled by the user on the map.
    CEL stage routes are always available as a separate overlay layer.
    """
    weather_year = request.session.get('weather_year', '')
    demand_year  = request.session.get('demand_year', '')
    scenario     = request.session.get('scenario', '')
    config_file  = request.session.get('config_file')
    success_message = ''

    if request.method == 'POST':
        demand_weather_scenario = DemandScenarioSettings(request.POST)
        if demand_weather_scenario.is_valid():
            demand_year = demand_weather_scenario.cleaned_data['demand_year']
            request.session['demand_year'] = demand_year
            scenario = demand_weather_scenario.cleaned_data['scenario']
            request.session['scenario'] = scenario
            success_message = 'Settings updated.'

    demand_weather_scenario = DemandScenarioSettings(initial={
        'demand_year': demand_year,
        'scenario': scenario,
    })

    # ── CEL stages (no scenario dependency) ────────────────────────────────
    cel_stages_data = []
    for stage in (
        CELStage.objects
        .filter(is_active=True)
        .select_related('cel_program')
        .order_by('cel_program__name', 'stage_number')
    ):
        coords = stage.get_route_coordinates()
        cel_stages_data.append({
            'id': stage.cel_stage_id,
            'name': stage.name,
            'program_name': stage.cel_program.name,
            'program_code': stage.cel_program.code,
            'funding_status': stage.funding_status,
            'funding_status_display': stage.get_funding_status_display(),
            'funding_status_weight': stage.funding_status_weight,
            'capacity_new_mw': stage.capacity_new_mw or 0,
            'capacity_unlocked_mw': stage.capacity_unlocked_existing_mw or 0,
            'total_capacity_mw': stage.total_capacity_mw,
            'reserved_capacity_mw': stage.reserved_capacity_mw or 0,
            'available_capacity_mw': stage.available_capacity_mw,
            'served_region': stage.served_region or '',
            'display_color': stage.display_color,
            'coordinates': coords,
        })

    # ── Best CEL alignment per facility ────────────────────────────────────
    best_alignment = {}
    for a in (
        FacilityCELAlignment.objects
        .filter(is_aligned=True)
        .select_related('cel_stage', 'cel_stage__cel_program')
    ):
        fid = a.facility_id
        score = a.viability_score or 0
        if fid not in best_alignment or score > (best_alignment[fid]['viability_score'] or 0):
            best_alignment[fid] = {
                'viability_score': a.viability_score,
                'viability_label': a.viability_label,
                'is_exception': a.is_exception,
                'cel_stage_name': a.cel_stage.name,
                'cel_stage_id': a.cel_stage_id,
                'program_code': a.cel_stage.cel_program.code,
                'distance_km': a.distance_to_route_km,
            }

    # ── Pipeline facilities (scenario-filtered) ────────────────────────────
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
                longitude__isnull=False,
            ).select_related('idtechnologies')

            for f in facilities_qs:
                retirement_year = None
                if f.commissioning_date and f.idtechnologies and f.idtechnologies.lifetime:
                    retirement_year = f.commissioning_date.year + int(f.idtechnologies.lifetime)

                category = (
                    f.idtechnologies.category
                    if f.idtechnologies and hasattr(f.idtechnologies, 'category')
                    else 'Unknown'
                )
                categories.add(category)

                probability = f.commissioning_probability if f.commissioning_probability is not None else 1.0
                status   = f.status if f.status else 'commissioned'
                capacity = float(f.capacity) if f.capacity else 0

                if f.commissioning_date:
                    cy = f.commissioning_date.year
                    year_min = cy if year_min is None else min(year_min, cy)
                    year_max = cy if year_max is None else max(year_max, cy)
                if retirement_year:
                    year_max = retirement_year if year_max is None else max(year_max, retirement_year)

                if status not in summary_stats:
                    summary_stats[status] = {'count': 0, 'total_mw': 0}
                summary_stats[status]['count']    += 1
                summary_stats[status]['total_mw'] += capacity

                a = best_alignment.get(f.idfacilities)
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
                    # CEL viability fields
                    'viability_label': a['viability_label'] if a else 'unscored',
                    'viability_score': a['viability_score'] if a else None,
                    'is_aligned': a is not None,
                    'is_exception': a['is_exception'] if a else False,
                    'cel_stage_name': a['cel_stage_name'] if a else None,
                    'program_code': a['program_code'] if a else None,
                    'distance_km': a['distance_km'] if a else None,
                })
        except Scenarios.DoesNotExist:
            pass

    # ── Grid lines ─────────────────────────────────────────────────────────
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

    # ── Terminals ──────────────────────────────────────────────────────────
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

    try:
        cel_summary = CELViabilityService.get_pipeline_summary()
    except Exception:
        cel_summary = None

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
        'cel_stages_json': json.dumps(cel_stages_data),
        'categories': json.dumps(sorted(categories)),
        'summary_stats_json': json.dumps(summary_stats),
        'cel_summary': cel_summary,
        'year_min': year_min,
        'year_max': year_max,
    }
    return render(request, 'cel_map.html', context)
