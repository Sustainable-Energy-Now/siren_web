# powermatchui/utils/esoo_forecast_adjustment.py
"""
Bias-corrected ESOO forecast anchors for Powermatch scenario building.

Sits between two already-working pieces:

  powerplotui.services.esoo_bias_analysis  -- align EsooFigure (forecast)
    against AnnualDemandActual (actual), compute mean error and a
    BiasVerdict per (metric, horizon) group, honestly refusing to assert
    a direction without enough evidence.

  powermatchui.views.esoo_scenario_views.resolve_esoo_anchors -- pulls the
    raw peak/minimum/energy anchors for a chosen (vintage, scenario, POE,
    forecast_year) straight from EsooFigure, which then feed the LDC/
    trace-synthesis/reconciliation pipeline into `supplyfactors`.

This module computes, for one raw anchor value, what that same
(metric, scenario, poe_level, horizon) group's historical bias implies it
should be corrected to -- and persists that as an EsooForecastAdjustment
row so every correction is traceable back to the exact statistic that
produced it (verdict, p-value, n), labelled by which analysis category
it belongs to (siren_web.models.ESOO_ADJUSTMENT_CATEGORY_CHOICES).

Only `growth_assumption` (the residual mean-error correction, computed
from data this project already has) is implemented here. The other
reserved categories -- weather_normalization, pv_recalibration,
block_load_removal, industrial_load_survey -- need data this project
doesn't have yet (a temperature series joined to demand, a Reserve
Capacity Price series, block-load/PV/LIL-specific actual-vs-forecast
series) and are manual-only until a pipeline exists for each.
"""
from dataclasses import dataclass, field
from typing import List, Optional

from powerplotui.services.esoo_bias_analysis import (
    ForecastActualPair,
    align_forecast_actual_pairs,
    assess_systematic_bias,
    melt_actual_to_metric_dicts,
    raw_errors_by_group,
)
from siren_web.models import AnnualDemandActual, EsooFigure, EsooForecastAdjustment

DEFAULT_CATEGORY = 'growth_assumption'


@dataclass
class AdjustedAnchor:
    metric: str
    horizon: int
    category: str
    original_value: float
    adjustment_value: float
    adjusted_value: float
    unit: str
    verdict: Optional[str]
    p_value: Optional[float]
    n: int
    notes: list = field(default_factory=list)


def compute_bias_correction(
    pairs: List[ForecastActualPair],
    metric: str,
    demand_growth_scenario: str,
    poe_level: Optional[int],
    horizon: int,
    original_value: float,
    unit: str,
    category: str = DEFAULT_CATEGORY,
) -> AdjustedAnchor:
    """
    Filters `pairs` to the (metric, demand_growth_scenario, poe_level)
    group at the given `horizon`, runs assess_systematic_bias on their
    historical errors, and applies the resulting correction to
    `original_value` -- a *new* forecast anchor being resolved for a
    scenario build, not one of the historical pairs itself.

    ForecastActualPair.error = forecast_value - actual_value, so a
    positive mean error (`me`) means historical forecasts of this type
    ran high; the correction subtracts it. Never applies a correction
    when the verdict is 'insufficient_evidence' -- same honesty principle
    as esoo_bias_analysis: reports zero adjustment with a clear reason,
    rather than "correcting" on statistical noise.
    """
    errors_by_group = raw_errors_by_group(
        pairs, demand_growth_scenario=demand_growth_scenario, poe_level=poe_level,
    )
    errors = errors_by_group.get((metric, horizon), [])
    verdict = assess_systematic_bias(errors)

    if verdict.verdict == 'insufficient_evidence':
        return AdjustedAnchor(
            metric=metric, horizon=horizon, category=category,
            original_value=original_value, adjustment_value=0.0, adjusted_value=original_value,
            unit=unit, verdict=verdict.verdict, p_value=verdict.p_value, n=verdict.n,
            notes=['No correction applied: insufficient evidence'] + verdict.notes,
        )

    adjustment_value = -verdict.me
    return AdjustedAnchor(
        metric=metric, horizon=horizon, category=category,
        original_value=original_value, adjustment_value=adjustment_value,
        adjusted_value=original_value + adjustment_value,
        unit=unit, verdict=verdict.verdict, p_value=verdict.p_value, n=verdict.n,
        notes=verdict.notes,
    )


def _persist_adjustment(source_figure, adjusted: AdjustedAnchor) -> EsooForecastAdjustment:
    """
    Idempotent, get-or-create by (source_figure, category) -- but never
    overwrites a row an analyst has manually edited (source='manual'),
    per the CRUD facility's override contract.
    """
    existing = EsooForecastAdjustment.objects.filter(
        source_figure=source_figure, category=adjusted.category,
    ).first()
    if existing is not None and existing.source == 'manual':
        return existing

    defaults = dict(
        horizon=adjusted.horizon,
        original_value=adjusted.original_value,
        adjustment_value=adjusted.adjustment_value,
        adjusted_value=adjusted.adjusted_value,
        unit=adjusted.unit,
        verdict=adjusted.verdict,
        p_value=adjusted.p_value,
        n=adjusted.n,
        methodology_notes='; '.join(adjusted.notes),
        source='computed',
    )
    obj, _ = EsooForecastAdjustment.objects.update_or_create(
        source_figure=source_figure, category=adjusted.category, defaults=defaults,
    )
    return obj


def load_figures_and_actuals():
    """
    Shapes the full demand-domain EsooFigure/AnnualDemandActual archive
    into the plain-dict form align_forecast_actual_pairs expects -- same
    query/shape as esoo_bias_views._build_extended_bias_report, factored
    out here so both callers stay in sync rather than drifting apart.
    """
    figures = [
        {
            'vintage_year': f.vintage.year, 'forecast_year': f.forecast_year, 'metric': f.metric,
            'demand_growth_scenario': f.demand_growth_scenario, 'poe_level': f.poe_level,
            'demand_basis': f.demand_basis, 'value': f.value, 'unit': f.unit,
        }
        # 'delivered' rows are crosswalk inputs, not forecasts comparable with any actual
        for f in EsooFigure.objects.filter(domain='demand').exclude(demand_basis='delivered').select_related('vintage')
    ]
    actuals = []
    for a in AnnualDemandActual.objects.all():
        actuals.extend(melt_actual_to_metric_dicts(a))
    return figures, actuals


def build_adjusted_anchors(
    vintage,
    esoo_scenario: str,
    forecast_year: int,
    anchor_figures: dict,
    figures=None,
    actuals=None,
    category: str = DEFAULT_CATEGORY,
):
    """
    Computes and persists a growth-assumption bias correction for each of
    the anchor EsooFigure rows already resolved by
    esoo_scenario_views.resolve_esoo_anchors (`anchor_figures`: a dict of
    {metric: EsooFigure} for whichever of peak_summer/peak_winter/energy/
    minimum were actually found).

    `figures`/`actuals` default to the full archive via
    load_figures_and_actuals() when not supplied; pass them explicitly
    (as in the unit tests) to use a fixed fixture instead.

    Returns {metric: AdjustedAnchor}. Each metric's correction is drawn
    from that metric's own (demand_growth_scenario, poe_level) group --
    poe_level is taken from each anchor figure itself (so an energy
    anchor resolved with no POE breakdown, poe_level=None, is corrected
    from that same no-POE-breakdown historical group, matching
    resolve_esoo_anchors' own energy fallback).
    """
    if figures is None or actuals is None:
        figures, actuals = load_figures_and_actuals()
    pairs, _refused = align_forecast_actual_pairs(figures, actuals)
    horizon = forecast_year - vintage.year

    results = {}
    for metric, figure in anchor_figures.items():
        anchor_poe = figure.poe_level  # None for a no-POE-breakdown energy anchor
        adjusted = compute_bias_correction(
            pairs, metric=metric, demand_growth_scenario=esoo_scenario,
            poe_level=anchor_poe, horizon=horizon,
            original_value=figure.value, unit=figure.unit, category=category,
        )
        _persist_adjustment(figure, adjusted)
        results[metric] = adjusted

    return results
