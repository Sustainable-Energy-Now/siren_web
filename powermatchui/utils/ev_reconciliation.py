# powermatchui/utils/ev_reconciliation.py
"""
FR-06/FR-07 — SWIS aggregation and the backcast gate.

FR-06 filters CSIRO postcode-level consumption to the SWIS set (via
SwisBoundaryMembership, D9) and aggregates to SWIS-wide annual energy per
(csiro_scenario, forecast_year). FR-07 is the plan's single most
important checkpoint (Section 8): the aggregate must reproduce CSIRO's
own published SWIS/WA aggregate within a *stated* tolerance before any
downstream use (trace synthesis, sensitivity comparison, tracking
report) is trusted. An undefined tolerance is recorded as not-yet-
validated -- never treated as passing by default (Phase 0 statistical-
honesty gate, same convention as powermatchui.utils.esoo_reconciliation).

This module takes plain dicts/values rather than Django querysets so it
stays unit-testable without a populated database, matching
powerplotui.services.esoo_bias_analysis's pattern.
"""
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple

DEFAULT_TOLERANCE_PCT = None  # Section 10 Open Item: exact FR-07 tolerance to be confirmed with the Sprint Leader


class BackcastNotValidatedError(ValueError):
    """Raised by require_backcast_passed() when a tolerance was never
    supplied/confirmed, or the aggregate fell outside it -- FR-07's hard
    gate: nothing downstream is trusted until this passes."""


@dataclass
class SwisAggregationResult:
    aggregated_mwh: Dict[Tuple[str, int], float]  # (csiro_scenario, forecast_year) -> MWh
    excluded_postcodes: List[str]  # postcodes with no SwisBoundaryMembership row -- excluded, not assumed 'in'
    n_figures_used: int


def aggregate_swis_annual_energy(
    figures: Iterable[dict], membership_by_postcode: Dict[str, dict],
) -> SwisAggregationResult:
    """
    FR-06. `figures`: iterable of dicts with postcode, forecast_year,
    csiro_scenario, consumption_kwh (one EvUptakePostcodeFigure row each,
    validation_status='passed' only -- filtering that is the caller's
    responsibility, per the Section 8 standing principle).

    `membership_by_postcode`: {postcode: {'membership_status': 'in'|'out'|
    'partial', 'apportionment_fraction': float}} (one SwisBoundaryMembership
    row each). A postcode with no membership row is excluded from the
    aggregate and reported separately, rather than silently assumed
    in-SWIS (obstacle O1: boundary leakage must be an explicit rule, not
    a default).
    """
    aggregated: Dict[Tuple[str, int], float] = {}
    excluded_postcodes: set = set()
    n_used = 0

    for f in figures:
        postcode = f['postcode']
        membership = membership_by_postcode.get(postcode)
        if membership is None:
            excluded_postcodes.add(postcode)
            continue

        status = membership['membership_status']
        if status == 'out':
            continue
        fraction = membership['apportionment_fraction'] if status == 'partial' else 1.0

        consumption_kwh = f.get('consumption_kwh')
        if consumption_kwh is None:
            continue

        key = (f['csiro_scenario'], f['forecast_year'])
        aggregated[key] = aggregated.get(key, 0.0) + (consumption_kwh * fraction) / 1000.0  # kWh -> MWh
        n_used += 1

    return SwisAggregationResult(
        aggregated_mwh=aggregated,
        excluded_postcodes=sorted(excluded_postcodes),
        n_figures_used=n_used,
    )


@dataclass
class BackcastCheck:
    csiro_scenario: str
    forecast_year: int
    aggregated_mwh: float
    published_mwh: Optional[float]
    tolerance_pct: Optional[float]
    status: str  # 'passed' | 'failed' | 'not_yet_validated'
    error_pct: Optional[float] = None
    notes: list = field(default_factory=list)


def run_backcast_gate(
    aggregation: SwisAggregationResult, published_aggregates_mwh: Dict[Tuple[str, int], float],
    tolerance_pct: Optional[float] = DEFAULT_TOLERANCE_PCT,
) -> List[BackcastCheck]:
    """
    FR-07. Compares each aggregated (scenario, year) against CSIRO's own
    published SWIS/WA aggregate for the same key. `tolerance_pct=None`
    (the default) means no tolerance has been confirmed yet -- every
    check comes back 'not_yet_validated', never 'passed' by default
    (Section 10 Open Item: the Sprint Leader must confirm this value
    before Phase 2 begins).
    """
    checks: List[BackcastCheck] = []
    for key, aggregated_mwh in sorted(aggregation.aggregated_mwh.items()):
        csiro_scenario, forecast_year = key
        published_mwh = published_aggregates_mwh.get(key)

        if published_mwh is None:
            checks.append(BackcastCheck(
                csiro_scenario=csiro_scenario, forecast_year=forecast_year,
                aggregated_mwh=aggregated_mwh, published_mwh=None, tolerance_pct=tolerance_pct,
                status='not_yet_validated', notes=["No published CSIRO aggregate available for this (scenario, year)"],
            ))
            continue

        if tolerance_pct is None:
            checks.append(BackcastCheck(
                csiro_scenario=csiro_scenario, forecast_year=forecast_year,
                aggregated_mwh=aggregated_mwh, published_mwh=published_mwh, tolerance_pct=None,
                status='not_yet_validated',
                notes=["FR-07 tolerance not yet confirmed (Section 10 Open Item) — never pass-by-default"],
            ))
            continue

        error_pct = abs(aggregated_mwh - published_mwh) / abs(published_mwh) * 100.0 if published_mwh else float('inf')
        status = 'passed' if error_pct <= tolerance_pct else 'failed'
        notes = [] if status == 'passed' else [f"error {error_pct:.4f}% exceeds tolerance {tolerance_pct}%"]
        checks.append(BackcastCheck(
            csiro_scenario=csiro_scenario, forecast_year=forecast_year,
            aggregated_mwh=aggregated_mwh, published_mwh=published_mwh, tolerance_pct=tolerance_pct,
            status=status, error_pct=error_pct, notes=notes,
        ))

    return checks


def require_backcast_passed(checks: List[BackcastCheck]) -> List[BackcastCheck]:
    """FR-07 hard gate: raise unless every check is 'passed'. Used by
    downstream callers (trace synthesis, sensitivity/tracking views) that
    must refuse to run against an unvalidated or failed backcast."""
    bad = [c for c in checks if c.status != 'passed']
    if bad:
        raise BackcastNotValidatedError(
            "FR-07 backcast gate not passed for: " + "; ".join(
                f"{c.csiro_scenario}/{c.forecast_year} ({c.status})" for c in bad
            )
        )
    return checks
