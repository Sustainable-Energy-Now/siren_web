from django.contrib.auth.decorators import login_required
from common.decorators import settings_required
from django.shortcuts import render
from siren_web.forms import DemandScenarioSettings
from siren_web.database_operations import fetch_module_settings_data, fetch_scenario_settings_data
from siren_web.models import facilities, Terminals, Scenarios, GridLines, FacilityGridConnections
import json


@login_required
@settings_required(redirect_view='powermapui:powermapui_home')
def infrastructure_network(request):
    """Full infrastructure dependency network showing all terminals, facilities, and grid lines."""
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

    nodes = []
    links = []
    bottlenecks = []
    terminal_pks = set()
    facility_pks = set()

    # Status summary
    status_summary = {}

    # Add ALL terminal nodes
    for t in Terminals.objects.filter(active=True).prefetch_related('outgoing_lines', 'incoming_lines'):
        total_connected_cap = t.calculate_total_connected_capacity()
        transformer_cap = float(t.transformer_capacity_mva) if t.transformer_capacity_mva else 0
        is_bottleneck = (total_connected_cap > transformer_cap) if transformer_cap > 0 else False

        nodes.append({
            'id': f'terminal_{t.pk}',
            'label': t.terminal_name,
            'type': 'terminal',
            'voltage': float(t.primary_voltage_kv) if t.primary_voltage_kv else 0,
            'transformer_capacity': transformer_cap,
            'total_connected_capacity': float(total_connected_cap),
            'is_bottleneck': is_bottleneck,
            'utilization_percent': t.get_utilization_percent(),
        })
        terminal_pks.add(t.pk)

        if is_bottleneck:
            bottlenecks.append({
                'terminal_name': t.terminal_name,
                'transformer_capacity_mva': transformer_cap,
                'connected_capacity_mw': float(total_connected_cap),
                'overload_mw': float(total_connected_cap - transformer_cap),
            })

    # Add facilities (filtered by scenario if set)
    fac_qs = facilities.objects.filter(
        latitude__isnull=False, longitude__isnull=False
    ).select_related('idtechnologies')
    if scenario:
        try:
            scenario_obj = Scenarios.objects.get(title=scenario)
            fac_qs = fac_qs.filter(scenarios=scenario_obj)
        except Scenarios.DoesNotExist:
            pass

    for f in fac_qs:
        retirement_year = None
        if f.commissioning_date and f.idtechnologies and f.idtechnologies.lifetime:
            retirement_year = f.commissioning_date.year + int(f.idtechnologies.lifetime)

        status = f.status if f.status else 'commissioned'
        probability = f.commissioning_probability if f.commissioning_probability is not None else 1.0
        capacity = float(f.capacity) if f.capacity else 0
        tech_name = f.idtechnologies.technology_name if f.idtechnologies else 'Unknown'
        tech_category = f.idtechnologies.category if f.idtechnologies and hasattr(f.idtechnologies, 'category') else 'Unknown'

        nodes.append({
            'id': f'facility_{f.pk}',
            'label': f.facility_name,
            'type': 'facility',
            'capacity': capacity,
            'status': status,
            'commissioning_probability': probability,
            'technology': tech_name,
            'technology_category': tech_category,
            'retirement_year': retirement_year,
        })
        facility_pks.add(f.pk)

        # Track summary
        if status not in status_summary:
            status_summary[status] = {'count': 0, 'total_mw': 0}
        status_summary[status]['count'] += 1
        status_summary[status]['total_mw'] += capacity

    # Add grid line links (terminal-to-terminal)
    for gl in GridLines.objects.filter(active=True).select_related('from_terminal', 'to_terminal'):
        if gl.from_terminal_id and gl.to_terminal_id:
            if gl.from_terminal_id in terminal_pks and gl.to_terminal_id in terminal_pks:
                links.append({
                    'source': f'terminal_{gl.from_terminal_id}',
                    'target': f'terminal_{gl.to_terminal_id}',
                    'type': 'gridline',
                    'line_type': gl.line_type,
                    'voltage': float(gl.voltage_level) if gl.voltage_level else 0,
                    'capacity': float(gl.thermal_capacity_mw) if gl.thermal_capacity_mw else 0,
                    'label': gl.line_name,
                })

    # Add facility-to-terminal links via FacilityGridConnections
    for conn in FacilityGridConnections.objects.filter(active=True).select_related('idgridlines', 'idgridlines__from_terminal', 'idgridlines__to_terminal'):
        fac_pk = conn.idfacilities_id
        if fac_pk not in facility_pks:
            continue
        gl = conn.idgridlines
        # Connect to whichever terminal exists on this grid line
        terminal_id = None
        if gl.from_terminal_id and gl.from_terminal_id in terminal_pks:
            terminal_id = f'terminal_{gl.from_terminal_id}'
        elif gl.to_terminal_id and gl.to_terminal_id in terminal_pks:
            terminal_id = f'terminal_{gl.to_terminal_id}'

        if terminal_id:
            links.append({
                'source': terminal_id,
                'target': f'facility_{fac_pk}',
                'type': 'facility_connection',
                'is_primary': conn.is_primary,
                'capacity': float(conn.connection_capacity_mw) if conn.connection_capacity_mw else 0,
            })

    network_data = {'nodes': nodes, 'links': links}

    terminal_count = sum(1 for n in nodes if n['type'] == 'terminal')
    facility_count = sum(1 for n in nodes if n['type'] == 'facility')

    context = {
        'demand_weather_scenario': demand_weather_scenario,
        'weather_year': weather_year,
        'demand_year': demand_year,
        'scenario': scenario,
        'config_file': config_file,
        'success_message': success_message,
        'network_data_json': json.dumps(network_data),
        'bottlenecks': bottlenecks,
        'bottlenecks_json': json.dumps(bottlenecks),
        'status_summary_json': json.dumps(status_summary),
        'node_count': len(nodes),
        'link_count': len(links),
        'terminal_count': terminal_count,
        'facility_count': facility_count,
        'bottleneck_count': len(bottlenecks),
    }
    return render(request, 'network_overview.html', context)
