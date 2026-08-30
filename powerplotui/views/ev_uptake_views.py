# powerplotui/views/ev_uptake_views.py
"""
FR-13/FR-14 presentation layer (Outcome B: early-warning tracking).
Wires powerplotui/services/ev_uptake_analysis.py onto real
EvUptakePostcodeFigure (projection side) / EvActualsRecord (actuals side)
data. Mirrors esoo_bias_views.py's presentation shape.
"""
import datetime as dt

import plotly.graph_objects as go
from django.shortcuts import render

from powerplotui.services.ev_uptake_analysis import build_tracking_report
from siren_web.models import EvActualsQuarter, EvActualsRecord, EvUptakePostcodeFigure

SCENARIO_COLORS = {'low': '#3498db', 'medium': '#f39c12', 'high': '#e74c3c'}
SCENARIO_LABELS = {'low': 'Low', 'medium': 'Medium', 'high': 'High'}


def _build_tracking_chart(curves, actuals_quarterly=None):
    if not curves and not actuals_quarterly:
        return ''

    fig = go.Figure()
    # Both series share a real date x-axis. CSIRO forecast_year is a
    # year-end fleet figure, so it is plotted at 31 Dec of that year —
    # which lines up exactly with the DoT December quarter.
    for scenario, curve in curves.items():
        years = sorted(curve.keys())
        fig.add_trace(go.Scatter(
            x=[dt.date(y, 12, 31) for y in years], y=[curve[y] for y in years],
            mode='lines+markers',
            name=f"CSIRO {SCENARIO_LABELS.get(scenario, scenario)}",
            line=dict(color=SCENARIO_COLORS.get(scenario, '#7f8c8d')),
            hovertext=[str(y) for y in years],
            hovertemplate='CSIRO %{hovertext}: %{y:,.0f}<extra></extra>',
        ))

    if actuals_quarterly:
        fig.add_trace(go.Scatter(
            x=[d for d, _ in actuals_quarterly], y=[t for _, t in actuals_quarterly],
            mode='lines+markers', name='WA actual (quarterly)',
            line=dict(color='#2c3e50', width=3, dash='dot'),
            marker=dict(size=7, symbol='diamond'),
            hovertext=[d.strftime('%b %Y') for d, _ in actuals_quarterly],
            hovertemplate='%{hovertext}: %{y:,.0f}<extra></extra>',
        ))

    fig.update_layout(
        title='WA EV fleet: CSIRO projections vs actuals (FR-13, like-for-like fleet counts)',
        xaxis_title='Quarter / forecast year-end', yaxis_title='EV fleet count',
        height=460, hovermode='x unified',
    )
    return fig.to_html(include_plotlyjs='cdn', div_id='ev_tracking_chart', full_html=False)


def ev_uptake_tracking(request):
    """FR-13/14 tracking dashboard. Only reads figures/actuals already
    marked validation_status='passed' -- the Section 8 standing principle
    also applies to this Outcome B view, not just Outcome A."""
    figures = list(
        EvUptakePostcodeFigure.objects.filter(validation_status='passed')
        .values('csiro_scenario', 'forecast_year', 'fleet_count')
    )
    actuals = list(EvActualsRecord.objects.filter(region='WA').values('year', 'fleet_count'))
    actuals_quarterly = [
        (q.period_end, q.total_count)
        for q in EvActualsQuarter.objects.filter(region='WA').order_by('period_end')
    ]

    report = build_tracking_report(figures, actuals)
    chart_html = _build_tracking_chart(report['curves'], actuals_quarterly)

    return render(request, 'ev_uptake/tracking.html', {
        'report': report,
        'chart_html': chart_html,
        'n_figures': len(figures),
        'n_actuals': len(actuals),
        'n_actuals_quarters': len(actuals_quarterly),
    })
