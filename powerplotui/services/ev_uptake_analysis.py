# powerplotui/services/ev_uptake_analysis.py
"""
FR-13/FR-14 — tracking-inversion statistics (Outcome B: early-warning
tracking). Pure functions over plain dicts, mirroring
esoo_bias_analysis.py's unit-testable style.

O8 (unit/geography asymmetry): the load model (Outcome A) runs on
consumption_kwh (D6), but WA actuals are only available as fleet counts
(D7) -- this module enforces the like-for-like fleet-vs-fleet comparison
FR-13's acceptance criterion requires, and never compares a fleet actual
against a consumption-based figure. It also aggregates EvUptakePostcodeFigure
state-wide (every postcode, not just SWIS-in ones), since the WA actuals
source is a state total (O4), not a SWIS-only one -- Outcome A's FR-06
SWIS filter does not apply here.
"""
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class TrajectoryFlag:
    year: int
    actual_fleet_count: float
    nearest_scenario: str
    divergence_fleet_count: float
    divergence_pct: float
    curves: Dict[str, float]


def aggregate_wa_fleet_by_scenario_year(figures) -> Dict[Tuple[str, int], float]:
    """
    `figures`: iterable of dicts with csiro_scenario, forecast_year,
    fleet_count (one EvUptakePostcodeFigure row each, validation_status=
    'passed' only -- filtering that is the caller's responsibility).
    State-wide sum (no SWIS-boundary filter — O8/O4).
    """
    totals: Dict[Tuple[str, int], float] = defaultdict(float)
    for f in figures:
        if f.get('fleet_count') is None:
            continue
        totals[(f['csiro_scenario'], f['forecast_year'])] += f['fleet_count']
    return dict(totals)


def build_projection_curves(fleet_totals: Dict[Tuple[str, int], float]) -> Dict[str, Dict[int, float]]:
    """Reshape {(scenario, year): fleet} into {scenario: {year: fleet}} — one curve per CSIRO scenario."""
    curves: Dict[str, Dict[int, float]] = defaultdict(dict)
    for (scenario, year), fleet in fleet_totals.items():
        curves[scenario][year] = fleet
    return dict(curves)


def flag_nearest_trajectory(year: int, actual_fleet_count: float, curves: Dict[str, Dict[int, float]]) -> Optional[TrajectoryFlag]:
    """
    FR-14. For a given actuals year, finds which CSIRO scenario curve WA's
    actual fleet count is nearest to. Returns None if no curve has a
    value for this exact year (never interpolates between forecast years).
    """
    year_values = {scenario: curve[year] for scenario, curve in curves.items() if year in curve}
    if not year_values:
        return None

    nearest_scenario = min(year_values, key=lambda s: abs(year_values[s] - actual_fleet_count))
    nearest_value = year_values[nearest_scenario]
    divergence = actual_fleet_count - nearest_value
    divergence_pct = (divergence / nearest_value * 100.0) if nearest_value else float('inf')

    return TrajectoryFlag(
        year=year, actual_fleet_count=actual_fleet_count, nearest_scenario=nearest_scenario,
        divergence_fleet_count=divergence, divergence_pct=divergence_pct, curves=year_values,
    )


def build_tracking_report(figures, actuals) -> dict:
    """
    Orchestrates FR-13 (projection curves + like-for-like alignment) and
    FR-14 (nearest-trajectory flag for the latest actuals year).
    `actuals`: iterable of dicts with year, fleet_count (one EvActualsRecord row each).
    """
    fleet_totals = aggregate_wa_fleet_by_scenario_year(figures)
    curves = build_projection_curves(fleet_totals)

    actuals_by_year = {a['year']: a['fleet_count'] for a in actuals}
    if not actuals_by_year:
        return {'curves': curves, 'actuals_by_year': {}, 'latest_flag': None}

    latest_year = max(actuals_by_year)
    latest_flag = flag_nearest_trajectory(latest_year, actuals_by_year[latest_year], curves)

    return {'curves': curves, 'actuals_by_year': actuals_by_year, 'latest_flag': latest_flag}
