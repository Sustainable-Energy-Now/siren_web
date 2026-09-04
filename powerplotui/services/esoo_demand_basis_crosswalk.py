# powerplotui/services/esoo_demand_basis_crosswalk.py
"""
FR-F07 (D13) -- Demand-definition crosswalk: derive an approximate
operational-basis annual energy figure from a published underlying-basis
one, by subtracting the real DPV (rooftop solar) contribution for the
matching WEM Capacity Year.

Scope, per D13: energy only. AEMO has never published peak or minimum
demand on the underlying basis anywhere in the ingested archive (confirmed
empirically -- zero such rows across every vintage), so no equivalent gap
exists for those metrics; this module does not touch them.

This is a narrow, explicitly-labelled exception to D3's default ("never
reconstruct operational from underlying") -- every row this module writes
is tagged extraction_method='dpv_subtraction' and carries a
human-readable reconciliation_adjustment record (FR-F04), so it is never
mistaken for a figure AEMO published directly.

Only produces a derived figure where real DPVGeneration data gives
adequate coverage of the target Capacity Year -- it does not fabricate a
growth-projected estimate for future years beyond DPV's real coverage
(D13 anticipates that as a possible follow-up; this module deliberately
stops short of it rather than inventing an unreviewed growth assumption).
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import pytz
from django.db.models import Sum

from siren_web.models import DPVGeneration, EsooFigure

AWST = pytz.timezone('Australia/Perth')

DEFAULT_MIN_COVERAGE_PCT = 95.0


class CrosswalkSkipped(Exception):
    """Raised (and caught by the caller) when a figure can't be crosswalked
    -- e.g. insufficient real DPV coverage for its Capacity Year. Not an
    error: this is FR-F07's "without fabricating precision" in action."""


@dataclass
class DpvCoverage:
    capacity_year_label: str
    annual_dpv_gwh: float
    interval_count: int
    expected_intervals: int
    coverage_pct: float


def _capacity_year_window(forecast_year: int):
    """WEM Capacity Year for an EsooFigure.forecast_year label: 1 Oct
    forecast_year 08:00 AWST -> 1 Oct forecast_year+1 08:00 AWST, matching
    compute_annual_demand_actuals.py's convention exactly."""
    start = AWST.localize(datetime(forecast_year, 10, 1, 8, 0, 0))
    end = AWST.localize(datetime(forecast_year + 1, 10, 1, 8, 0, 0))
    return start, end


def compute_dpv_annual_energy(forecast_year: int, min_coverage_pct: float = DEFAULT_MIN_COVERAGE_PCT) -> DpvCoverage:
    """
    Aggregate real DPVGeneration data into an annual energy total (GWh)
    for the Capacity Year forecast_year-(forecast_year+1).

    Raises CrosswalkSkipped if coverage is below min_coverage_pct -- e.g.
    a forecast year beyond DPVGeneration's real data range (currently
    2024-01-01 onward), or a year DPV ingestion hasn't fully backfilled.
    """
    start, end = _capacity_year_window(forecast_year)
    label = f"{forecast_year}-{str(forecast_year + 1)[-2:]}"

    qs = DPVGeneration.objects.filter(trading_interval__gte=start, trading_interval__lt=end)
    interval_count = qs.values('trading_interval').distinct().count()
    expected_intervals = round((end - start).total_seconds() / 1800)
    coverage_pct = (interval_count / expected_intervals * 100) if expected_intervals else 0.0

    if coverage_pct < min_coverage_pct:
        raise CrosswalkSkipped(
            f"Capacity Year {label}: only {interval_count}/{expected_intervals} DPV intervals "
            f"({coverage_pct:.1f}%) -- below --min-coverage {min_coverage_pct}%. No growth-projected "
            f"estimate is used as a substitute (D13 scope); skipping."
        )

    # estimated_generation is genuine MW (verified against a real solar
    # curve, unlike FacilityScada's half-hourly-energy convention) -- so
    # energy per interval = MW * 0.5h.
    total_mw = qs.aggregate(total=Sum('estimated_generation'))['total'] or 0
    annual_dpv_mwh = float(total_mw) * 0.5
    annual_dpv_gwh = annual_dpv_mwh / 1000.0

    return DpvCoverage(
        capacity_year_label=label,
        annual_dpv_gwh=annual_dpv_gwh,
        interval_count=interval_count,
        expected_intervals=expected_intervals,
        coverage_pct=coverage_pct,
    )


def derive_operational_energy_figure(underlying_figure: EsooFigure, min_coverage_pct: float = DEFAULT_MIN_COVERAGE_PCT) -> dict:
    """
    Build the field values for a derived operational-basis EsooFigure row
    from one published underlying-basis energy figure.

    Raises CrosswalkSkipped (propagated from compute_dpv_annual_energy)
    where DPV coverage is inadequate -- callers should catch this and
    move on rather than treating it as fatal.
    """
    if underlying_figure.metric != 'energy':
        raise ValueError(f"Crosswalk is energy-only (D13); got metric={underlying_figure.metric!r}")
    if underlying_figure.demand_basis != 'underlying':
        raise ValueError(f"Expected demand_basis='underlying'; got {underlying_figure.demand_basis!r}")
    if (underlying_figure.unit or '').strip().upper() != 'GWH':
        raise ValueError(
            f"Underlying figure (id={underlying_figure.idesoofigure}) has unexpected unit "
            f"'{underlying_figure.unit}'; expected GWh -- refusing to guess a conversion."
        )

    coverage = compute_dpv_annual_energy(underlying_figure.forecast_year, min_coverage_pct)
    derived_value = underlying_figure.value - coverage.annual_dpv_gwh

    adjustment_note = (
        f"D13 crosswalk: operational energy derived as underlying ({underlying_figure.value:,.2f} GWh) "
        f"minus real DPV generation for Capacity Year {coverage.capacity_year_label} "
        f"({coverage.annual_dpv_gwh:,.2f} GWh, {coverage.coverage_pct:.1f}% interval coverage from "
        f"DPVGeneration) = {derived_value:,.2f} GWh. Not a figure AEMO published directly -- see "
        f"extraction_method."
    )

    return {
        'vintage': underlying_figure.vintage,
        'domain': underlying_figure.domain,
        'metric': underlying_figure.metric,
        'forecast_year': underlying_figure.forecast_year,
        'demand_growth_scenario': underlying_figure.demand_growth_scenario,
        'poe_level': underlying_figure.poe_level,
        'demand_basis': 'operational',
        'value': derived_value,
        'unit': underlying_figure.unit,
        'source_document': underlying_figure.source_document,
        'source_version': underlying_figure.source_version,
        'table_ref': underlying_figure.table_ref,
        'page_ref': underlying_figure.page_ref,
        'cell_ref': underlying_figure.cell_ref,
        'extraction_date': underlying_figure.extraction_date,
        'extraction_method': 'dpv_subtraction',
        'reconciliation_adjustment': adjustment_note,
    }
