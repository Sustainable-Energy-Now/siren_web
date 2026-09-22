# powermatchui/views/scenario_summary_views.py
"""
Read-only summary of a scenario's Load (demand) trace: annual energy, peak and
minimum with their times, load factor, monthly energy, mean daily profile,
peak-day profile and load-duration curve, plus how the scenario was built and an
optional side-by-side comparison with a second scenario.

Nothing here writes to the database. The statistics live in
powermatchui/utils/scenario_summary.py; this module only finds the scenario's
Load facilities and traces (SupplyFactorMatrix), calls that, and draws charts.
"""
from typing import List, Optional

import numpy as np
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render

from powermatchui.utils.scenario_summary import (
    LoadStats,
    LoadTraceError,
    compare_stats,
    describe_provenance,
    sum_traces,
    summarise_load_trace,
)
from siren_web.models import Scenarios, SupplyFactorMatrix, facilities
from siren_web.services.supply_matrix import facility_trace

MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']


class NoLoadTraceError(ValueError):
    """The scenario has no Load facility with a trace for the requested year."""


def _load_facility_q() -> Q:
    return Q(idtechnologies__category='Load') | Q(idtechnologies__technology_name='Load')


def load_facilities(scenario: Scenarios) -> List[facilities]:
    return list(
        facilities.objects.filter(scenarios=scenario).filter(_load_facility_q()).distinct().order_by('facility_name')
    )


def years_with_trace(facility_ids) -> List[int]:
    """Years in SupplyFactorMatrix that have a row for any of these facilities."""
    wanted = set(facility_ids)
    return [
        row.year for row in SupplyFactorMatrix.objects.defer('data').order_by('year')
        if wanted & set(row.facility_ids)
    ]


def scenarios_with_load() -> List[Scenarios]:
    load_ids = facilities.objects.filter(_load_facility_q()).values_list('idfacilities', flat=True)
    return list(
        Scenarios.objects.filter(scenariosfacilities__idfacilities__in=list(load_ids)).distinct().order_by('title')
    )


def scenario_load(scenario: Scenarios, year: int):
    """(total Load trace in MW, per-facility rows) for a scenario and year.
    Raises NoLoadTraceError / LoadTraceError with a message fit to show the user."""
    facs = load_facilities(scenario)
    if not facs:
        raise NoLoadTraceError(f"Scenario '{scenario.title}' has no Load facility.")
    traces, rows = [], []
    for fac in facs:
        try:
            trace = facility_trace(year, fac.idfacilities)
        except SupplyFactorMatrix.DoesNotExist:
            trace = None
        if trace is None or np.all(np.isnan(np.asarray(trace, dtype=float))):
            continue
        traces.append(np.asarray(trace, dtype=float))
        try:
            s = summarise_load_trace(trace, year)
            rows.append({'name': fac.facility_name, 'energy_gwh': s.annual_energy_gwh, 'peak_mw': s.peak_mw,
                         'minimum_mw': s.minimum_mw})
        except LoadTraceError as e:
            rows.append({'name': fac.facility_name, 'error': str(e)})
    if not traces:
        raise NoLoadTraceError(f"Scenario '{scenario.title}' has no Load trace for {year}.")
    if len({t.size for t in traces}) > 1:
        raise LoadTraceError("This scenario's Load facilities have traces of different lengths for this year.")
    return (traces[0] if len(traces) == 1 else sum_traces(traces)), rows


def _hours_axis(stats: LoadStats) -> List[float]:
    return [i * stats.interval_hours for i in range(stats.intervals_per_day)]


def _time_axis(fig, title):
    ticks = list(range(0, 25, 3))
    fig.update_layout(
        title=title, height=340, margin=dict(l=50, r=20, t=50, b=40), hovermode='x unified',
        xaxis=dict(title='Time of day', tickmode='array', tickvals=ticks, ticktext=[f"{h:02d}:00" for h in ticks],
                   range=[0, 24]),
        yaxis=dict(title='MW'),
    )


def build_charts(a: LoadStats, name_a: str, b: Optional[LoadStats] = None, name_b: str = '') -> dict:
    import plotly.graph_objects as go

    series = [(a, name_a, '#2c3e50')] + ([(b, name_b, '#e67e22')] if b else [])
    charts, first = {}, True

    def html(fig, div_id):
        nonlocal first
        out = fig.to_html(include_plotlyjs='cdn' if first else False, full_html=False, div_id=div_id)
        first = False
        return out

    fig = go.Figure()
    for stats, name, colour in series:
        fig.add_trace(go.Scatter(x=_hours_axis(stats), y=stats.mean_daily_profile_mw, mode='lines', name=name,
                                 line=dict(color=colour, width=2)))
    _time_axis(fig, 'Mean daily profile')
    charts['profile'] = html(fig, 'summary_profile')

    fig = go.Figure()
    for stats, name, colour in series:
        fig.add_trace(go.Scatter(x=_hours_axis(stats), y=stats.peak_day_profile_mw, mode='lines',
                                 name=f"{name}: {stats.peak_day:%d %b}", line=dict(color=colour, width=2)))
    _time_axis(fig, "Peak day (each scenario's own highest-demand day)")
    charts['peak_day'] = html(fig, 'summary_peak_day')

    fig = go.Figure()
    for i, (stats, name, colour) in enumerate(series):
        fig.add_trace(go.Bar(x=MONTHS, y=stats.monthly_energy_gwh, name=name, marker_color=colour))
    fig.update_layout(title='Monthly energy', height=340, barmode='group', margin=dict(l=50, r=20, t=50, b=40),
                      yaxis=dict(title='GWh'))
    charts['monthly'] = html(fig, 'summary_monthly')

    fig = go.Figure()
    for stats, name, colour in series:
        fig.add_trace(go.Scatter(x=list(range(len(stats.duration_curve_mw))), y=stats.duration_curve_mw, mode='lines',
                                 name=name, line=dict(color=colour, width=2)))
    fig.update_layout(title='Load-duration curve', height=340, hovermode='x unified',
                      margin=dict(l=50, r=20, t=50, b=40),
                      xaxis=dict(title='% of the year demand is at or above this level'), yaxis=dict(title='MW'))
    charts['duration'] = html(fig, 'summary_duration')
    return charts


def _int_or_none(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@login_required
def scenario_summary(request):
    """GET-only: ?scenario=<id>&year=<yyyy>&compare=<id> (all optional)."""
    all_scenarios = scenarios_with_load()
    selected_id = _int_or_none(request.GET.get('scenario'))
    compare_id = _int_or_none(request.GET.get('compare'))
    selected_year = _int_or_none(request.GET.get('year'))

    context = {
        'scenarios': all_scenarios, 'selected_id': selected_id, 'compare_id': compare_id,
        'selected_year': selected_year, 'years': [], 'error': None,
    }
    if selected_id is None:
        return render(request, 'scenario_summary.html', context)

    scenario = next((s for s in all_scenarios if s.idscenarios == selected_id), None)
    if scenario is None:
        context['error'] = "That scenario doesn't exist or has no Load facility."
        return render(request, 'scenario_summary.html', context)

    fac_ids = [f.idfacilities for f in load_facilities(scenario)]
    years = years_with_trace(fac_ids)
    context['years'] = years
    if not years:
        context['error'] = f"'{scenario.title}' has no stored Load trace in any year."
        return render(request, 'scenario_summary.html', context)
    year = selected_year if selected_year in years else years[-1]
    context['selected_year'] = year

    try:
        trace, facility_rows = scenario_load(scenario, year)
        stats = summarise_load_trace(trace, year)
    except (NoLoadTraceError, LoadTraceError) as e:
        context['error'] = str(e)
        return render(request, 'scenario_summary.html', context)

    other, other_stats, comparison = None, None, None
    if compare_id is not None and compare_id != selected_id:
        other = next((s for s in all_scenarios if s.idscenarios == compare_id), None)
        if other is None:
            context['error'] = "The comparison scenario doesn't exist or has no Load facility."
        else:
            try:
                other_trace, _ = scenario_load(other, year)
                other_stats = summarise_load_trace(other_trace, year)
                comparison = compare_stats(stats, other_stats)
            except (NoLoadTraceError, LoadTraceError) as e:
                context['error'] = f"Comparison: {e}"
                other = None

    context.update({
        'scenario': scenario, 'stats': stats, 'facility_rows': facility_rows,
        'provenance': describe_provenance(scenario.description, scenario.interval_minutes, scenario.reference_year),
        'other': other, 'other_stats': other_stats, 'comparison': comparison,
        'charts': build_charts(stats, scenario.title or f"Scenario {scenario.idscenarios}",
                               other_stats, (other.title if other else '') or ''),
        'resolution': 'half-hourly' if stats.intervals_per_day == 48 else 'hourly',
    })
    return render(request, 'scenario_summary.html', context)
