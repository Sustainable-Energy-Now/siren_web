# powerplotui/views/ev_uptake_views.py
"""
FR-13/FR-14 presentation layer (Outcome B: early-warning tracking).
Wires powerplotui/services/ev_uptake_analysis.py onto real
EvUptakePostcodeFigure (projection side) / EvActualsRecord (actuals side)
data. Mirrors esoo_bias_views.py's presentation shape.
"""
import plotly.graph_objects as go
from django.shortcuts import render

from powerplotui.services.ev_uptake_analysis import build_tracking_report
from siren_web.models import EvActualsRecord, EvUptakePostcodeFigure

SCENARIO_COLORS = {'low': '#3498db', 'medium': '#f39c12', 'high': '#e74c3c'}
SCENARIO_LABELS = {'low': 'Low', 'medium': 'Medium', 'high': 'High'}


def _build_tracking_chart(curves, actuals_by_year):
    if not curves and not actuals_by_year:
        return ''

    fig = go.Figure()
    for scenario, curve in curves.items():
        years = sorted(curve.keys())
        fig.add_trace(go.Scatter(
            x=years, y=[curve[y] for y in years], mode='lines+markers',
            name=f"CSIRO {SCENARIO_LABELS.get(scenario, scenario)}",
            line=dict(color=SCENARIO_COLORS.get(scenario, '#7f8c8d')),
        ))

    if actuals_by_year:
        years = sorted(actuals_by_year.keys())
        fig.add_trace(go.Scatter(
            x=years, y=[actuals_by_year[y] for y in years], mode='lines+markers',
            name='WA actual', line=dict(color='#2c3e50', width=3, dash='dot'),
            marker=dict(size=9, symbol='diamond'),
        ))

    fig.update_layout(
        title='WA EV fleet: CSIRO projections vs actuals (FR-13, like-for-like fleet counts)',
        xaxis_title='Year', yaxis_title='EV fleet count',
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

    report = build_tracking_report(figures, actuals)
    chart_html = _build_tracking_chart(report['curves'], report['actuals_by_year'])

    return render(request, 'ev_uptake/tracking.html', {
        'report': report,
        'chart_html': chart_html,
        'n_figures': len(figures),
        'n_actuals': len(actuals),
    })
