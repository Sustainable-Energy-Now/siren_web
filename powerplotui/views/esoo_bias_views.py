# powerplotui/views/esoo_bias_views.py
"""
FR-G2 presentation layer. Wires powerplotui/services/esoo_bias_analysis.py
(Phase 2, already unit-tested) onto real EsooFigure/AnnualDemandActual data,
gated behind a validation-first backcast against AEMO's own published
forecast-vs-actual comparison (D11/FR-G2-06).

Two things happen on this page, in a strict order:

1. `_validate_against_table11()` reproduces AEMO's own stated
   forecast-vs-actual gaps for three specific events published in Table 11
   of the 2026 WEM ESOO (p.40 -- "Actual unscheduled operational demand
   compared with 2025 WEM ESOO Expected scenario forecasts"), using this
   project's own alignment/error functions, and reports whether they match.
   This runs entirely off numbers extracted directly from that PDF table
   (both the "forecast" and the "actual" side come from the same table) --
   it does NOT depend on EsooFigure/AnnualDemandActual being populated
   correctly, which matters because this sandbox has no way to verify that
   independently (no DB access).
2. Only then does the page show the "extended" archive-wide bias tracking
   built from the real EsooFigure (forecast side) and AnnualDemandActual
   (actual side, populated by compute_annual_demand_actuals) tables.

Table 11 is deliberately NOT wired into esoo_pdf_parser.FIGURE_EXTRACTORS --
its shape (three named events x four rows) doesn't fit the scenario/POE-axis
figures that machinery is built for, and it belongs to G2's validation step
(Phase 3b), not the Foundation's per-vintage figure store. See
esoo_pdf_parser's module docstring, which flags it as "a strong candidate
for D11/FR-G2-06's validation-first backcast reference" -- this is that.
"""
import logging
from collections import defaultdict
from pathlib import Path

import plotly.graph_objects as go
from django.conf import settings
from django.shortcuts import render

from powerplotui.services.esoo_bias_analysis import (
    align_forecast_actual_pairs,
    assess_systematic_bias,
    compute_band_calibration,
    compute_central_estimate_errors,
)
from powerplotui.services.esoo_pdf_parser import (
    _find_table_by_row_label,
    _row_lookup,
    _to_number,
    extract_raw_tables,
)
from siren_web.models import AnnualDemandActual, EsooFigure, EsooVintage

logger = logging.getLogger(__name__)

VERDICT_COLORS = {
    'forecasts_run_high': '#e74c3c',
    'forecasts_run_low': '#3498db',
    'insufficient_evidence': '#95a5a6',
}
VERDICT_LABELS = {
    'forecasts_run_high': 'Forecasts run high',
    'forecasts_run_low': 'Forecasts run low',
    'insufficient_evidence': 'Insufficient evidence',
}
METRIC_LABELS = {
    'energy': 'Annual energy',
    'peak_summer': 'Peak demand (summer)',
    'peak_winter': 'Peak demand (winter)',
    'minimum': 'Minimum demand',
}

# The single event this table gives an explicit numeric gap for in prose
# ("...winter peak demand reaching 3,953 MW, around 177 MW above the
# corresponding 10% POE forecast of 3,776 MW") -- used as the exact-match
# check. The other two events are only described qualitatively ("fell
# between the 10% and 50% POE ... levels" / "between the 50% and 90% POE
# ... levels") -- used as band-placement checks instead of exact matches,
# to avoid claiming more precision than AEMO's own text provides.
TABLE11_EVENT_META = {
    'Winter maximum 2024-25': {
        'metric': 'peak_winter', 'forecast_year': 2024,
        'check': 'exact', 'check_poe': 10, 'aemo_gap_mw': 177,
        'quote': '"...winter peak demand reaching 3,953 MW, around 177 MW above the '
                 'corresponding 10% POE forecast of 3,776 MW."',
    },
    'Annual minimum 2024-25': {
        'metric': 'minimum', 'forecast_year': 2024,
        'check': 'band', 'band_poe_lo': 50, 'band_poe_hi': 10,
        'quote': '"Actual OPSO demand fell between the 10% and 50% POE minimum '
                 'unscheduled operational demand forecast levels..."',
    },
    'Summer maximum 2025-26': {
        'metric': 'peak_summer', 'forecast_year': 2025,
        'check': 'band', 'band_poe_lo': 90, 'band_poe_hi': 50,
        'quote': '"...unscheduled operational demand outcomes between the 50% and 90% '
                 'POE forecast levels from the 2025 WEM ESOO."',
    },
}
TABLE11_REFERENCE_VINTAGE_YEAR = 2025  # Table 11 compares against "2025 WEM ESOO ... forecasts"


def _extract_table11_events(vintage):
    """
    Ad hoc extraction of Table 11 (p.40 of the 2026 WEM ESOO). Reuses
    esoo_pdf_parser's generic table utilities (extract_raw_tables,
    _find_table_by_row_label, _row_lookup, _to_number) since this is
    the same style of pdfplumber table this project already knows how to
    walk -- but the event/metric mapping here is specific to this one
    validation exercise, not a general-purpose figure extractor.
    """
    pdf_path = Path(settings.ESOO_ARCHIVE_DIR) / vintage.local_file_path
    # Table 11 is confirmed on p.40 of the 2026 WEM ESOO; scope extraction
    # to that page (+/- 1 for safety margin) instead of scanning all 128
    # pages. This view runs on every page load with no caching, and an
    # unscoped scan takes minutes -- long enough to time out the request
    # and, via pdfplumber/pdfminer's per-token DEBUG logging, flood the
    # production log in the process. If a future vintage moves this table,
    # _find_table_by_row_label below will simply fail to find it and raise
    # the "Table 11 not found" error rather than silently miss it.
    raw_tables = extract_raw_tables(pdf_path, pages=[39, 40, 41])

    header = _find_table_by_row_label(raw_tables, 'Actuals')
    if header is None:
        raise ValueError(
            "Table 11 not found (no row starting 'Actuals') on pages 39-41 -- PDF layout "
            "may have changed since this was last inspected."
        )

    rows = _row_lookup(header)
    event_labels = rows.get('Actuals')
    trading_intervals = rows.get('Trading Interval starting')
    actuals = rows.get('Operational sent out (OPSO) (MW)')
    poe10 = rows.get('10% POE (MW)')
    poe50 = rows.get('50% POE (MW)')
    poe90 = rows.get('90% POE (MW)')

    missing = [
        name for name, val in [
            ('Actuals', event_labels), ('Trading Interval starting', trading_intervals),
            ('Operational sent out (OPSO) (MW)', actuals), ('10% POE (MW)', poe10),
            ('50% POE (MW)', poe50), ('90% POE (MW)', poe90),
        ] if not val
    ]
    if missing:
        raise ValueError(f"Table 11 found but missing expected row(s): {missing} -- inspect PDF layout again.")

    events = []
    for i, label in enumerate(event_labels):
        meta = TABLE11_EVENT_META.get(label)
        if meta is None:
            logger.warning(f"Table 11 extractor: unrecognised event column '{label}', skipping")
            continue
        events.append({
            'label': label,
            'metric': meta['metric'],
            'forecast_year': meta['forecast_year'],
            'trading_interval': trading_intervals[i],
            'actual_mw': _to_number(actuals[i]),
            'poe10_mw': _to_number(poe10[i]),
            'poe50_mw': _to_number(poe50[i]),
            'poe90_mw': _to_number(poe90[i]),
            'meta': meta,
        })
    return events


def _validate_against_table11():
    """
    FR-G2-06/D11 validation-first backcast. Returns a dict with
    status='ok'|'error' and, on success, per-event rows showing:
      - the raw extracted numbers,
      - the error computed by this pipeline's own ForecastActualPair/
        align_forecast_actual_pairs machinery (POE10/50/90, so the exact
        band AEMO's prose references can be checked, not just POE50),
      - whether that reproduces what AEMO's own text states,
      - and, separately, what compute_central_estimate_errors (POE50, this
        project's own "central estimate" convention -- D12(a)) gives for
        the same three events, clearly labelled as a distinct comparison
        AEMO's prose does not itself state a number for.
    """
    try:
        vintage_2026 = EsooVintage.objects.get(year=2026)
    except EsooVintage.DoesNotExist:
        return {
            'status': 'error',
            'message': 'EsooVintage 2026 not found -- run `manage.py ingest_esoo_vintage --year 2026` first.',
        }

    if not vintage_2026.local_file_path:
        return {
            'status': 'error',
            'message': 'EsooVintage 2026 has no local_file_path -- the PDF has not been retrieved.',
        }

    try:
        events = _extract_table11_events(vintage_2026)
    except Exception as e:
        return {'status': 'error', 'message': str(e)}

    if len(events) != 3:
        return {
            'status': 'error',
            'message': f'Expected 3 Table 11 events, extracted {len(events)}: {[e["label"] for e in events]}',
        }

    # Build ForecastActualPair-shaped dicts across all three POE bands (not
    # just POE50) so the exact band AEMO's prose references can be checked.
    figures, actuals = [], []
    for e in events:
        actuals.append({
            'forecast_year': e['forecast_year'], 'metric': e['metric'],
            'demand_basis': 'operational', 'value': e['actual_mw'],
        })
        for poe, val in ((10, e['poe10_mw']), (50, e['poe50_mw']), (90, e['poe90_mw'])):
            figures.append({
                'vintage_year': TABLE11_REFERENCE_VINTAGE_YEAR, 'forecast_year': e['forecast_year'],
                'metric': e['metric'], 'demand_growth_scenario': 'expected', 'poe_level': poe,
                'demand_basis': 'operational', 'value': val, 'unit': 'MW',
            })

    pairs, refused = align_forecast_actual_pairs(figures, actuals)
    pairs_by_metric_poe = {(p.metric, p.poe_level): p for p in pairs}

    event_rows = []
    all_match = True
    for e in events:
        meta = e['meta']
        metric = e['metric']
        p10 = pairs_by_metric_poe.get((metric, 10))
        p50 = pairs_by_metric_poe.get((metric, 50))
        p90 = pairs_by_metric_poe.get((metric, 90))

        if meta['check'] == 'exact':
            check_pair = pairs_by_metric_poe.get((metric, meta['check_poe']))
            computed_gap = abs(check_pair.error) if check_pair else None
            matched = computed_gap is not None and abs(computed_gap - meta['aemo_gap_mw']) < 0.5
            detail = (
                f"POE{meta['check_poe']} forecast {check_pair.forecast_value:.0f} MW vs actual "
                f"{check_pair.actual_value:.0f} MW -> computed gap {computed_gap:.0f} MW "
                f"(AEMO states {meta['aemo_gap_mw']} MW)"
            ) if check_pair else "pair not found"
        else:  # 'band'
            lo_pair = pairs_by_metric_poe.get((metric, meta['band_poe_lo']))
            hi_pair = pairs_by_metric_poe.get((metric, meta['band_poe_hi']))
            if lo_pair and hi_pair:
                lo_val, hi_val = sorted([lo_pair.forecast_value, hi_pair.forecast_value])
                actual = lo_pair.actual_value
                matched = lo_val <= actual <= hi_val
                detail = (
                    f"actual {actual:.0f} MW vs POE{meta['band_poe_hi']}={hi_pair.forecast_value:.0f} MW / "
                    f"POE{meta['band_poe_lo']}={lo_pair.forecast_value:.0f} MW -> "
                    f"{'within' if matched else 'OUTSIDE'} stated band [{lo_val:.0f}, {hi_val:.0f}]"
                )
            else:
                matched = False
                detail = "pair(s) not found"
            computed_gap = None

        all_match = all_match and matched
        event_rows.append({
            'label': e['label'], 'metric': metric, 'metric_label': METRIC_LABELS.get(metric, metric),
            'trading_interval': e['trading_interval'], 'actual_mw': e['actual_mw'],
            'poe10_mw': e['poe10_mw'], 'poe50_mw': e['poe50_mw'], 'poe90_mw': e['poe90_mw'],
            'quote': meta['quote'], 'check_type': meta['check'], 'matched': matched, 'detail': detail,
            'central_estimate_error': (p50.error if p50 else None),
        })

    return {
        'status': 'ok',
        'all_match': all_match,
        'events': event_rows,
        'refused': refused,
        'vintage_year': vintage_2026.year,
        'reference_vintage_year': TABLE11_REFERENCE_VINTAGE_YEAR,
    }


def _melt_actual_to_metric_dicts(actual):
    """
    AnnualDemandActual has one row per (year, demand_basis) with WIDE
    columns (annual_energy_gwh, peak_demand_mw, minimum_demand_mw) -- not
    one row per metric like EsooFigure. But EsooFigure separates peak into
    'peak_summer'/'peak_winter' (two distinct forecast series), while
    AnnualDemandActual only stores a single annual peak_demand_mw. Those
    don't line up 1:1: a single calendar year genuinely has both a summer
    peak event and a winter peak event, but this schema only records
    whichever one turned out to be the higher of the two.

    Rather than silently comparing that single actual peak against BOTH
    peak_summer and peak_winter forecasts (which would be wrong for
    whichever season it didn't occur in), this tags the actual peak with
    the season implied by its own peak_datetime (per the 2026 WEM ESOO's
    own season definitions, p.30: summer = Dec-Mar, winter = Jun-Aug) and
    only emits a dict for that one metric. Years whose peak falls in a
    shoulder month (Apr/May/Sep-Nov) emit no peak metric at all -- there is
    no honest way to attribute it to either forecast series, and
    align_forecast_actual_pairs treats "no actual" as "not yet scoreable",
    not an error.

    This is a real, currently-unresolved gap between the two schemas: this
    project cannot validate a 'peak_winter' AND a 'peak_summer' forecast
    for the same year from AnnualDemandActual as it stands, only whichever
    one happened to be the annual max. Flagged in the Phase 3b report.
    """
    out = []
    if actual.annual_energy_gwh is not None:
        out.append({
            'forecast_year': actual.year, 'metric': 'energy',
            'demand_basis': actual.demand_basis, 'value': actual.annual_energy_gwh,
        })
    if actual.minimum_demand_mw is not None:
        out.append({
            'forecast_year': actual.year, 'metric': 'minimum',
            'demand_basis': actual.demand_basis, 'value': actual.minimum_demand_mw,
        })
    if actual.peak_demand_mw is not None and actual.peak_datetime is not None:
        month = actual.peak_datetime.month
        if month in (12, 1, 2, 3):
            peak_metric = 'peak_summer'
        elif month in (6, 7, 8):
            peak_metric = 'peak_winter'
        else:
            peak_metric = None  # shoulder month -- not attributable to either series
        if peak_metric:
            out.append({
                'forecast_year': actual.year, 'metric': peak_metric,
                'demand_basis': actual.demand_basis, 'value': actual.peak_demand_mw,
            })
    return out


def _central_estimate_errors_by_group(pairs):
    """
    Raw per-pair signed errors grouped by (metric, horizon), central
    estimate only (same filter as esoo_bias_analysis._is_central_estimate:
    D12(a) -- Expected scenario, POE50 where a POE axis applies). Kept
    separately from compute_central_estimate_errors() because that
    function only returns aggregated me/mae/n, and assess_systematic_bias
    needs the raw list to run its t-test.
    """
    grouped = defaultdict(list)
    for p in pairs:
        if p.demand_growth_scenario == 'expected' and (p.poe_level is None or p.poe_level == 50):
            grouped[(p.metric, p.horizon)].append(p.error)
    return grouped


def _build_extended_bias_report():
    """
    FR-G2-03/04/08 extended, archive-wide bias report from real EsooFigure
    (forecast side) and AnnualDemandActual (actual side, from
    compute_annual_demand_actuals). Returns None if AnnualDemandActual is
    still empty (nothing to report yet -- distinct from an error).
    """
    if not AnnualDemandActual.objects.exists():
        return None

    figures = [
        {
            'vintage_year': f.vintage.year, 'forecast_year': f.forecast_year, 'metric': f.metric,
            'demand_growth_scenario': f.demand_growth_scenario, 'poe_level': f.poe_level,
            'demand_basis': f.demand_basis, 'value': f.value, 'unit': f.unit,
        }
        for f in EsooFigure.objects.filter(domain='demand').select_related('vintage')
    ]
    actuals = []
    for a in AnnualDemandActual.objects.all():
        actuals.extend(_melt_actual_to_metric_dicts(a))

    pairs, refused = align_forecast_actual_pairs(figures, actuals)

    central_stats = compute_central_estimate_errors(pairs)
    grouped_errors = _central_estimate_errors_by_group(pairs)

    bias_rows = []
    for key in sorted(central_stats.keys()):
        metric, horizon = key
        stats = central_stats[key]
        errors = grouped_errors.get(key, [])
        verdict = assess_systematic_bias(errors)
        pct_errors = [
            (p.error / p.actual_value * 100) for p in pairs
            if (p.metric, p.horizon) == key
            and p.demand_growth_scenario == 'expected' and (p.poe_level is None or p.poe_level == 50)
            and p.actual_value
        ]
        bias_rows.append({
            'metric': metric, 'metric_label': METRIC_LABELS.get(metric, metric), 'horizon': horizon,
            'n': stats['n'], 'me': stats['me'], 'mae': stats['mae'], 'unit': stats['unit'],
            'me_pct': (sum(pct_errors) / len(pct_errors)) if pct_errors else None,
            'verdict': verdict.verdict, 'verdict_label': VERDICT_LABELS[verdict.verdict],
            'p_value': verdict.p_value, 'notes': '; '.join(verdict.notes),
        })

    # Band calibration: minimum's exceedance direction is unresolved
    # (spec OQ-3) -- exclude it here rather than guess (compute_band_
    # calibration raises ValueError if 'minimum' pairs are present without
    # an explicit minimum_direction).
    non_minimum_pairs = [p for p in pairs if p.metric != 'minimum']
    minimum_excluded_n = sum(
        1 for p in pairs if p.metric == 'minimum' and p.demand_growth_scenario == 'expected' and p.poe_level is not None
    )
    calibration = compute_band_calibration(non_minimum_pairs)
    calibration_rows = [
        {
            'metric': metric, 'metric_label': METRIC_LABELS.get(metric, metric), 'poe': poe,
            'n': stats['n'], 'realised_frequency': stats['realised_frequency'],
            'nominal_frequency': stats['nominal_frequency'], 'direction': stats['direction'],
        }
        for (metric, poe), stats in sorted(calibration.items())
    ]

    return {
        'bias_rows': bias_rows,
        'calibration_rows': calibration_rows,
        'refused': refused,
        'minimum_excluded_n': minimum_excluded_n,
        'n_figures': len(figures),
        'n_actuals': len(actuals),
        'n_pairs': len(pairs),
    }


def _build_bias_chart(bias_rows):
    """% mean error by metric/horizon, central estimate only. Percentage
    (not raw ME) so metrics with different native units (GWh vs MW) can
    share one y-axis without a unit-mixing anti-pattern; raw ME/MAE in
    native units is shown alongside in the stats table."""
    rows_with_pct = [r for r in bias_rows if r['me_pct'] is not None]
    if not rows_with_pct:
        return ''

    x_labels = [f"{r['metric_label']}<br>+{r['horizon']}y (n={r['n']})" for r in rows_with_pct]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=x_labels,
        y=[r['me_pct'] for r in rows_with_pct],
        marker_color=[VERDICT_COLORS[r['verdict']] for r in rows_with_pct],
        text=[r['verdict_label'] for r in rows_with_pct],
        hovertemplate='%{x}<br>Mean %% error: %{y:.1f}%%<br>%{text}<extra></extra>',
    ))
    fig.add_hline(y=0, line_color='#7f8c8d', line_width=1)
    fig.update_layout(
        title='Central-estimate forecast bias by metric & horizon (mean %% error, forecast vs actual)',
        yaxis_title='Mean error (%% of actual)',
        height=420,
        showlegend=False,
    )
    return fig.to_html(include_plotlyjs='cdn', div_id='bias_me_chart', full_html=False)


def _build_calibration_chart(calibration_rows):
    """Realised vs nominal exceedance frequency by metric/POE band."""
    if not calibration_rows:
        return ''

    x_labels = [f"{r['metric_label']}<br>POE{r['poe']} (n={r['n']})" for r in calibration_rows]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        name='Nominal (expected)',
        x=x_labels,
        y=[r['nominal_frequency'] for r in calibration_rows],
        marker_color='#bdc3c7',
    ))
    fig.add_trace(go.Bar(
        name='Realised (observed)',
        x=x_labels,
        y=[r['realised_frequency'] for r in calibration_rows],
        marker_color='#3498db',
    ))
    fig.update_layout(
        title='Band calibration: realised vs nominal exceedance frequency',
        yaxis_title='Exceedance frequency',
        yaxis_tickformat='.0%',
        barmode='group',
        height=420,
        hovermode='x unified',
    )
    return fig.to_html(include_plotlyjs=False, div_id='bias_calibration_chart', full_html=False)


def bias_tracking_dashboard(request):
    """
    FR-G2 presentation view. Validation-first: the Table 11 backcast is
    always computed and shown; the extended archive-wide section only
    renders once AnnualDemandActual has data (populated separately by
    `manage.py compute_annual_demand_actuals`).
    """
    table11 = _validate_against_table11()
    extended = _build_extended_bias_report()

    bias_chart_html = ''
    calibration_chart_html = ''
    if extended:
        bias_chart_html = _build_bias_chart(extended['bias_rows'])
        calibration_chart_html = _build_calibration_chart(extended['calibration_rows'])

    return render(request, 'esoo_bias/bias_tracking.html', {
        'table11': table11,
        'extended': extended,
        'bias_chart_html': bias_chart_html,
        'calibration_chart_html': calibration_chart_html,
    })
