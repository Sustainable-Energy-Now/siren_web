# powermatchui/views/scenario_summary_views.py
"""
Read-only summary of a Demand's trace: annual energy, peak and minimum with
their times, load factor, monthly energy, mean daily profile, peak-day
profile and load-duration curve, plus how the Demand was built and an
optional side-by-side comparison with a second Demand.

Nothing here writes to the database. The statistics live in
powermatchui/utils/scenario_summary.py; this module only finds Demand
records and their traces (DemandMatrix), calls that, and draws charts.
"""
from typing import List, Optional

import numpy as np
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from powermatchui.utils.scenario_summary import (
    LoadStats,
    LoadTraceError,
    compare_stats,
    describe_provenance,
    summarise_load_trace,
)
from siren_web.models import Demand, DemandMatrix
from siren_web.services.demand_matrix import demand_trace

MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']


class NoLoadTraceError(ValueError):
    """The Demand has no trace for the requested year."""


def demands_with_trace() -> List[Demand]:
    return list(Demand.objects.filter(is_active=True).order_by('name'))


def years_with_trace(demand_id) -> List[int]:
    """Years in DemandMatrix that have a row for this demand."""
    return [
        row.year for row in DemandMatrix.objects.defer('data').order_by('year')
        if demand_id in row.demand_ids
    ]


def scenario_load(demand: Demand, year: int):
    """The Demand's trace in MW for a given year.
    Raises NoLoadTraceError / LoadTraceError with a message fit to show the user."""
    try:
        trace = demand_trace(year, demand.iddemand)
    except DemandMatrix.DoesNotExist:
        trace = None
    if trace is None or np.all(np.isnan(np.asarray(trace, dtype=float))):
        raise NoLoadTraceError(f"Demand '{demand.name}' has no trace for {year}.")
    return np.asarray(trace, dtype=float)


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
    """GET-only: ?scenario=<id>&year=<yyyy>&compare=<id> (all optional; ids are Demand ids)."""
    all_scenarios = demands_with_trace()
    selected_id = _int_or_none(request.GET.get('scenario'))
    compare_id = _int_or_none(request.GET.get('compare'))
    selected_year = _int_or_none(request.GET.get('year'))

    context = {
        'scenarios': all_scenarios, 'selected_id': selected_id, 'compare_id': compare_id,
        'selected_year': selected_year, 'years': [], 'error': None,
    }
    if selected_id is None:
        return render(request, 'scenario_summary.html', context)

    scenario = next((s for s in all_scenarios if s.iddemand == selected_id), None)
    if scenario is None:
        context['error'] = "That Demand doesn't exist."
        return render(request, 'scenario_summary.html', context)

    years = years_with_trace(scenario.iddemand)
    context['years'] = years
    if not years:
        context['error'] = f"'{scenario.name}' has no stored trace in any year."
        return render(request, 'scenario_summary.html', context)
    year = selected_year if selected_year in years else years[-1]
    context['selected_year'] = year

    try:
        trace = scenario_load(scenario, year)
        stats = summarise_load_trace(trace, year)
    except (NoLoadTraceError, LoadTraceError) as e:
        context['error'] = str(e)
        return render(request, 'scenario_summary.html', context)

    other, other_stats, comparison = None, None, None
    if compare_id is not None and compare_id != selected_id:
        other = next((s for s in all_scenarios if s.iddemand == compare_id), None)
        if other is None:
            context['error'] = "The comparison Demand doesn't exist."
        else:
            try:
                other_trace = scenario_load(other, year)
                other_stats = summarise_load_trace(other_trace, year)
                comparison = compare_stats(stats, other_stats)
            except (NoLoadTraceError, LoadTraceError) as e:
                context['error'] = f"Comparison: {e}"
                other = None

    context.update({
        'scenario': scenario, 'stats': stats,
        'provenance': describe_provenance(scenario),
        'other': other, 'other_stats': other_stats, 'comparison': comparison,
        'charts': build_charts(stats, scenario.name or f"Demand {scenario.iddemand}",
                               other_stats, (other.name if other else '') or ''),
        'resolution': 'half-hourly' if stats.intervals_per_day == 48 else 'hourly',
    })
    return render(request, 'scenario_summary.html', context)
