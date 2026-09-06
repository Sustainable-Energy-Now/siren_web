# powerplotui/views/ev_charging_views.py
"""
Display of the AEMO Step Change EV charging profiles (EvChargingProfile,
FR-03) that drive the half-hourly EV load model — the raw per-charging-
type weekday/weekend shapes, and the unmanaged vs managed composites that
powermatchui.utils.ev_trace_synthesis.combine_charging_type_shapes builds
from them.

Read-only. Does not run trace synthesis against a year's energy — just
shows the shapes and shares themselves, with explanation.
"""
import plotly.graph_objects as go
from django.shortcuts import render

from powermatchui.utils.ev_trace_synthesis import (
    TraceSynthesisError,
    ChargingTypeProfile,
    combine_charging_type_shapes,
)
from siren_web.models import EvChargingProfile

INTERVALS_PER_DAY = 48

MODE_COLOURS = {
    'unmanaged': '#e74c3c',
    'managed': '#27ae60',
    'v2x': '#8e44ad',
    'other': '#95a5a6',
}
MODE_LABELS = {
    'unmanaged': 'Unmanaged (plug-in on arrival)',
    'managed': 'Managed (TOU / off-peak / coordinated)',
    'v2x': 'Vehicle-to-home / Vehicle-to-grid',
    'other': 'Unclassified',
}

# 00:00, 00:30, … 23:30
_TIME_LABELS = [f"{(i * 30) // 60:02d}:{(i * 30) % 60:02d}" for i in range(INTERVALS_PER_DAY)]


def _peak_time(shape):
    """Half-hour label carrying the most charging energy."""
    if not shape:
        return '—'
    return _TIME_LABELS[max(range(len(shape)), key=lambda i: shape[i])]


def _shape_figure(profiles, attr, title):
    """One line per charging type: fraction of that type's daily charging
    energy falling in each half-hour."""
    fig = go.Figure()
    for p in profiles:
        shape = getattr(p, attr)
        fig.add_trace(go.Scatter(
            x=_TIME_LABELS, y=shape, mode='lines', name=p.charging_type_label,
            line=dict(color=MODE_COLOURS.get(p.charging_mode, '#7f8c8d'),
                      dash='dot' if p.charging_mode in ('managed', 'v2x') else 'solid'),
            hovertemplate=f"{p.charging_type_label}<br>%{{x}}: %{{y:.3f}}<extra></extra>",
        ))
    fig.update_layout(
        title=title, xaxis_title='Time of day', yaxis_title='Share of daily charging energy',
        height=420, hovermode='x unified',
        xaxis=dict(tickmode='array', tickvals=_TIME_LABELS[::4]),
        legend=dict(orientation='h', yanchor='bottom', y=-0.45),
    )
    return fig


def _composite_figure(composites):
    """Unmanaged vs managed composite weekday shapes on one axis — the
    shapes combine_charging_type_shapes actually feeds the load model."""
    fig = go.Figure()
    for mode, weekday, _weekend in composites:
        fig.add_trace(go.Scatter(
            x=_TIME_LABELS, y=list(weekday), mode='lines',
            name=f"{MODE_LABELS.get(mode, mode)} composite",
            line=dict(color=MODE_COLOURS.get(mode, '#7f8c8d'), width=3),
            hovertemplate=f"{mode}<br>%{{x}}: %{{y:.4f}}<extra></extra>",
        ))
    fig.update_layout(
        title='Composite weekday charging shape: unmanaged vs managed '
              '(share-weighted, the shapes fed to the EV load model)',
        xaxis_title='Time of day', yaxis_title='Share of daily charging energy',
        height=420, hovermode='x unified',
        xaxis=dict(tickmode='array', tickvals=_TIME_LABELS[::4]),
    )
    return fig


def ev_charging_profiles(request):
    qs = list(
        EvChargingProfile.objects.select_related('source_document', 'source_document__ev_vintage')
        .order_by('region', 'charging_mode', '-share_of_charging')
    )

    profiles = [
        ChargingTypeProfile(
            charging_type_label=p.charging_type_label, charging_mode=p.charging_mode,
            share_of_charging=p.share_of_charging,
            weekday_shape=p.weekday_halfhourly_shape, weekend_shape=p.weekend_halfhourly_shape,
        )
        for p in qs
    ]

    def _source_label(p):
        vintage = getattr(p.source_document, 'ev_vintage', None)
        parts = [p.report_citation or (vintage.version if vintage else '')]
        if p.citation_year:
            parts.append(f"{p.citation_year} snapshot")
        if p.table_ref:
            parts.append(p.table_ref)
        return ', '.join(part for part in parts if part) or '—'

    rows = []
    for p, ctp in zip(qs, profiles):
        rows.append({
            'region': p.region,
            'charging_type_label': p.charging_type_label,
            'charging_mode': p.charging_mode,
            'charging_mode_label': MODE_LABELS.get(p.charging_mode, p.charging_mode),
            'share_of_charging': p.share_of_charging,
            'weekday_peak': _peak_time(p.weekday_halfhourly_shape),
            'weekend_peak': _peak_time(p.weekend_halfhourly_shape),
        })

    # Region and source are identical across every row in practice (one
    # AEMO workbook, one region) — surfaced as a caption above the table
    # rather than a repeated column.
    regions = sorted({p.region for p in qs})
    sources = sorted({_source_label(p) for p in qs})

    # Composites — only for modes the synthesis code actually consumes.
    composites, composite_notes = [], []
    for mode in ('unmanaged', 'managed'):
        try:
            weekday, weekend = combine_charging_type_shapes(profiles, mode)
            composites.append((mode, weekday, weekend))
        except TraceSynthesisError as e:
            composite_notes.append(f"{MODE_LABELS.get(mode, mode)}: {e}")

    # Share not covered by any static shape (e.g. AEMO "TOU Dynamic Charging").
    modes_present = {p.charging_mode for p in profiles}
    total_share = sum(p.share_of_charging for p in profiles)

    charts = []
    if profiles:
        charts.append(_shape_figure(profiles, 'weekday_shape', 'Weekday charging shape by charging type')
                      .to_html(include_plotlyjs='cdn', full_html=False, div_id='ev_weekday_chart'))
        charts.append(_shape_figure(profiles, 'weekend_shape', 'Weekend charging shape by charging type')
                      .to_html(include_plotlyjs=False, full_html=False, div_id='ev_weekend_chart'))
    if composites:
        charts.append(_composite_figure(composites)
                      .to_html(include_plotlyjs=False, full_html=False, div_id='ev_composite_chart'))

    return render(request, 'ev_charging/profiles.html', {
        'rows': rows,
        'charts': charts,
        'n_profiles': len(rows),
        'regions': regions,
        'sources': sources,
        'total_share': total_share,
        'modes_present': sorted(modes_present),
        'composite_notes': composite_notes,
        'mode_labels': MODE_LABELS,
    })
