"""
SWIS RET Replacement Scenarios Analysis Views

Analytical framework for assessing how different RET levels (55–85%) displace
coal and gas generation in WA's SWIS by 2030. Benchmarks are stored in the
[ret_analysis] section of the active .ini config file.
"""

import os
import json
import logging
from configparser import ConfigParser, NoSectionError, NoOptionError

from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required

logger = logging.getLogger(__name__)

CONFIG_DIR = './siren_web/siren_files/preferences/'
DEFAULT_CONFIG_FILE = 'siren.ini'
SECTION = 'ret_analysis'
RET_LEVELS = [55, 60, 65, 70, 75, 80, 85]

DEFAULTS = {
    'expected_demand_twh': '20',
    'high_demand_twh': '22',
    'wind_capacity_factor': '0.40',
    'solar_capacity_factor': '0.25',
    'current_re_baseline_gwh': '5600',
    'pipeline_wind_gw': '2.07',
    'pipeline_solar_gw': '0.55',
    'fossil_count': '8',
    'fossil_1': 'Synergy coal - Muja,2946,1,coal',
    'fossil_2': 'Synergy coal - Collie,871,2,coal',
    'fossil_3': 'Bluewaters coal (non-Synergy),1783,3,coal',
    'fossil_4': 'Synergy gas - Pinjar,538,4,gas',
    'fossil_5': 'Synergy gas - Kwinana,843,5,gas',
    'fossil_6': 'Synergy gas - Cockburn,797,6,gas',
    'fossil_7': 'Synergy gas - WK + Mungarra,11,7,gas',
    'fossil_8': 'Other (non-Synergy) gas,4841,8,gas',
}


def _get_config_path(request):
    config_file = request.session.get('config_file') or DEFAULT_CONFIG_FILE
    return os.path.join(CONFIG_DIR, config_file)


def get_ret_config(config_path):
    """Read [ret_analysis] from ini, falling back to DEFAULTS for missing keys."""
    cfg = ConfigParser()
    cfg.read(config_path)

    def _get(key):
        try:
            return cfg.get(SECTION, key)
        except (NoSectionError, NoOptionError):
            return DEFAULTS.get(key, '')

    fossil_count = int(_get('fossil_count') or 8)
    fossil_sources = []
    for i in range(1, fossil_count + 1):
        raw = _get(f'fossil_{i}')
        if not raw:
            continue
        parts = [p.strip() for p in raw.split(',')]
        if len(parts) < 4:
            continue
        fossil_sources.append({
            'key': f'fossil_{i}',
            'name': parts[0],
            'gwh': float(parts[1]),
            'priority': int(parts[2]),
            'fuel_type': parts[3],
        })
    fossil_sources.sort(key=lambda x: x['priority'])

    return {
        'expected_demand_twh': float(_get('expected_demand_twh') or 20),
        'high_demand_twh': float(_get('high_demand_twh') or 22),
        'wind_capacity_factor': float(_get('wind_capacity_factor') or 0.40),
        'solar_capacity_factor': float(_get('solar_capacity_factor') or 0.25),
        'current_re_baseline_gwh': float(_get('current_re_baseline_gwh') or 5600),
        'pipeline_wind_gw': float(_get('pipeline_wind_gw') or 2.07),
        'pipeline_solar_gw': float(_get('pipeline_solar_gw') or 0.55),
        'fossil_count': fossil_count,
        'fossil_sources': fossil_sources,
    }


def save_ret_config(config_path, post_data):
    """Write [ret_analysis] section to the ini file, preserving other sections."""
    cfg = ConfigParser()
    cfg.read(config_path)

    if not cfg.has_section(SECTION):
        cfg.add_section(SECTION)

    scalar_keys = [
        'expected_demand_twh', 'high_demand_twh',
        'wind_capacity_factor', 'solar_capacity_factor',
        'current_re_baseline_gwh', 'pipeline_wind_gw', 'pipeline_solar_gw',
    ]
    for key in scalar_keys:
        val = post_data.get(key, '').strip()
        if val:
            cfg.set(SECTION, key, val)

    # Rebuild fossil sources from POSTed lists
    names = post_data.getlist('fossil_name')
    gwhs = post_data.getlist('fossil_gwh')
    priorities = post_data.getlist('fossil_priority')
    fuel_types = post_data.getlist('fossil_fuel_type')

    count = len(names)
    cfg.set(SECTION, 'fossil_count', str(count))

    # Remove old fossil keys
    existing_keys = [k for k in cfg.options(SECTION) if k.startswith('fossil_') and k != 'fossil_count']
    for k in existing_keys:
        cfg.remove_option(SECTION, k)

    for i, (name, gwh, priority, fuel_type) in enumerate(
        zip(names, gwhs, priorities, fuel_types), start=1
    ):
        name = name.strip()
        if not name:
            continue
        cfg.set(SECTION, f'fossil_{i}', f'{name},{gwh.strip()},{priority.strip()},{fuel_type.strip()}')

    with open(config_path, 'w') as f:
        cfg.write(f)


def compute_displacement(additional_needed, fossil_sources):
    """
    Displace fossil sources in priority order until additional_needed is exhausted.
    Returns a list with displaced_gwh and residual_gwh for each source.
    """
    remaining = additional_needed
    result = []
    for source in fossil_sources:
        if remaining <= 0:
            displaced = 0.0
        elif remaining >= source['gwh']:
            displaced = source['gwh']
        else:
            displaced = remaining
        residual = source['gwh'] - displaced
        remaining -= displaced
        result.append({
            'name': source['name'],
            'fuel_type': source['fuel_type'],
            'total_gwh': source['gwh'],
            'displaced_gwh': round(displaced, 0),
            'residual_gwh': round(residual, 0),
        })
    return result


def compute_ret_analysis(demand_twh, ret_config):
    """
    For a given demand (TWh), compute the displacement analysis for each RET level.
    Returns a list of row dicts.
    """
    demand_gwh = demand_twh * 1000
    baseline = ret_config['current_re_baseline_gwh']
    wind_cf = ret_config['wind_capacity_factor']
    solar_cf = ret_config['solar_capacity_factor']
    wind_gw = ret_config['pipeline_wind_gw']
    solar_gw = ret_config['pipeline_solar_gw']

    pipeline_wind_gwh = wind_gw * 1000 * wind_cf * 8760 / 1000
    pipeline_solar_gwh = solar_gw * 1000 * solar_cf * 8760 / 1000
    pipeline_total_gwh = pipeline_wind_gwh + pipeline_solar_gwh

    fossil_sources = ret_config['fossil_sources']

    rows = []
    for ret_pct in RET_LEVELS:
        required_re = round(demand_gwh * ret_pct / 100, 0)
        additional_needed = round(required_re - baseline, 0)
        feasibility_gap = required_re - (baseline + pipeline_total_gwh)

        if feasibility_gap <= 0:
            feasibility_text = f"Met by pipeline (surplus {abs(feasibility_gap):,.0f} GWh)"
            feasibility_class = 'feasible'
        elif feasibility_gap <= 1000:
            feasibility_text = f"Tight — gap {feasibility_gap:,.0f} GWh"
            feasibility_class = 'tight'
        else:
            feasibility_text = f"Shortfall {feasibility_gap:,.0f} GWh"
            feasibility_class = 'shortfall'

        displacement = compute_displacement(additional_needed, fossil_sources)

        displaced_coal = sum(d['displaced_gwh'] for d in displacement if d['fuel_type'] == 'coal')
        displaced_gas = sum(d['displaced_gwh'] for d in displacement if d['fuel_type'] == 'gas')
        residual_coal = sum(d['residual_gwh'] for d in displacement if d['fuel_type'] == 'coal')
        residual_gas = sum(d['residual_gwh'] for d in displacement if d['fuel_type'] == 'gas')

        rows.append({
            'ret_pct': ret_pct,
            'required_re_gwh': required_re,
            'additional_needed_gwh': additional_needed,
            'feasibility_gap': round(feasibility_gap, 0),
            'feasibility_text': feasibility_text,
            'feasibility_class': feasibility_class,
            'displacement': displacement,
            'displaced_coal': displaced_coal,
            'displaced_gas': displaced_gas,
            'residual_coal': residual_coal,
            'residual_gas': residual_gas,
            'baseline_re': baseline,
        })

    return rows


def _build_chart_data(rows, demand_label):
    """Build Plotly horizontal stacked bar chart data for one demand forecast."""
    ret_labels = [f"{r['ret_pct']}%" for r in rows]

    baseline_re = [r['baseline_re'] for r in rows]
    additional_re_coal = [r['displaced_coal'] for r in rows]
    additional_re_gas = [r['displaced_gas'] for r in rows]
    residual_coal = [r['residual_coal'] for r in rows]
    residual_gas = [r['residual_gas'] for r in rows]

    traces = [
        {
            'type': 'bar', 'orientation': 'h',
            'name': 'RE Baseline', 'x': baseline_re, 'y': ret_labels,
            'marker': {'color': '#2ecc71'},
        },
        {
            'type': 'bar', 'orientation': 'h',
            'name': 'Additional RE displacing coal', 'x': additional_re_coal, 'y': ret_labels,
            'marker': {'color': '#27ae60'},
        },
        {
            'type': 'bar', 'orientation': 'h',
            'name': 'Additional RE displacing gas', 'x': additional_re_gas, 'y': ret_labels,
            'marker': {'color': '#82e0aa'},
        },
        {
            'type': 'bar', 'orientation': 'h',
            'name': 'Residual coal', 'x': residual_coal, 'y': ret_labels,
            'marker': {'color': '#2c3e50'},
        },
        {
            'type': 'bar', 'orientation': 'h',
            'name': 'Residual gas', 'x': residual_gas, 'y': ret_labels,
            'marker': {'color': '#95a5a6'},
        },
    ]

    layout = {
        'barmode': 'stack',
        'title': f'Generation Mix by RET Level — {demand_label}',
        'xaxis': {'title': 'GWh', 'tickformat': ','},
        'yaxis': {'title': 'RET Level', 'autorange': 'reversed'},
        'legend': {'orientation': 'h', 'y': -0.25},
        'margin': {'l': 60, 'r': 20, 't': 50, 'b': 80},
        'height': 380,
    }

    return {'data': traces, 'layout': layout}


def ret_analysis_dashboard(request):
    """Main RET Replacement Scenarios analysis view."""
    config_path = _get_config_path(request)
    ret_config = get_ret_config(config_path)

    expected_demand = ret_config['expected_demand_twh']
    high_demand = ret_config['high_demand_twh']

    rows_expected = compute_ret_analysis(expected_demand, ret_config)
    rows_high = compute_ret_analysis(high_demand, ret_config)

    chart_expected = _build_chart_data(rows_expected, f'{expected_demand:.0f} TWh Expected')
    chart_high = _build_chart_data(rows_high, f'{high_demand:.0f} TWh High')

    fossil_headers = [s['name'] for s in ret_config['fossil_sources']]

    context = {
        'expected_demand': expected_demand,
        'high_demand': high_demand,
        'rows_expected': rows_expected,
        'rows_high': rows_high,
        'fossil_headers': fossil_headers,
        'chart_expected_json': json.dumps(chart_expected),
        'chart_high_json': json.dumps(chart_high),
        'config_file': request.session.get('config_file', DEFAULT_CONFIG_FILE),
    }
    return render(request, 'ret_analysis/dashboard.html', context)

@login_required
def ret_analysis_config(request):
    """CRUD view for [ret_analysis] config parameters."""
    config_path = _get_config_path(request)

    if request.method == 'POST':
        try:
            save_ret_config(config_path, request.POST)
            messages.success(request, 'RET analysis configuration saved successfully.')
        except Exception as e:
            logger.error('Error saving RET analysis config: %s', e, exc_info=True)
            messages.error(request, f'Error saving configuration: {e}')
        return redirect('ret_analysis_config')

    ret_config = get_ret_config(config_path)
    context = {
        'ret_config': ret_config,
        'config_file': request.session.get('config_file', DEFAULT_CONFIG_FILE),
    }
    return render(request, 'ret_analysis/config.html', context)
