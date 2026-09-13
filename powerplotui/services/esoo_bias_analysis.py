# powerplotui/services/esoo_bias_analysis.py
"""
FR-G2-02/03/04/08 — bias-tracking statistics.

Pure functions operating on plain forecast/actual records (not Django
querysets) so they're unit-testable without AnnualDemandActual being
populated yet (that's Phase 3b — SCADA-derived actuals). Once it exists,
the caller just needs to shape EsooFigure/AnnualDemandActual rows into the
dict forms these functions expect.

Design choices this module makes explicit, matching the requirements spec
directly rather than leaving them implicit:

- FR-G2-02 (alignment): mismatched demand_basis is refused, not silently
  compared (obstacle O5) — align_forecast_actual_pairs() returns refused
  pairs separately with a reason, rather than dropping them silently.
- D12(a)/FR-G2-03 (central-estimate lens): "central estimate" means the
  Expected scenario, and POE50 where a POE axis exists (peak/minimum) —
  energy has no POE axis, so Expected alone defines it there.
- Minimum demand's POE exceedance direction is NOT assumed (spec OQ-3 is
  still open) — compute_band_calibration() requires minimum_direction to
  be passed explicitly for the 'minimum' metric rather than guessing.
- GR-5/FR-G2-08 (statistical honesty): assess_systematic_bias() requires
  both a minimum sample size AND a one-sample t-test p-value below alpha
  before asserting a directional verdict; otherwise it reports
  'insufficient_evidence' rather than 'no bias' or 'bias' (FR-G2-08's AC).
  DEFAULT_MIN_SAMPLE_SIZE=5 resolves OQ-6 as an explicit, overridable
  default: below 5 samples a t-test has essentially no power, so this is
  a floor, not a claim that 5 is sufficient for confidence — GR-3 (accrue
  evidence over time) means this improves as the archive grows.
"""
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy import stats

DEFAULT_MIN_SAMPLE_SIZE = 5
DEFAULT_ALPHA = 0.05


@dataclass
class ForecastActualPair:
    vintage_year: int
    forecast_year: int
    horizon: int
    metric: str
    demand_growth_scenario: str
    poe_level: Optional[int]
    demand_basis: str
    forecast_value: float
    actual_value: float
    unit: str

    @property
    def error(self) -> float:
        """Signed error: positive means the forecast ran high."""
        return self.forecast_value - self.actual_value


def align_forecast_actual_pairs(figures, actuals) -> Tuple[List[ForecastActualPair], List[dict]]:
    """
    FR-G2-02. `figures`: iterable of dicts with vintage_year, forecast_year,
    metric, demand_growth_scenario, poe_level, demand_basis, value, unit
    (one EsooFigure row each). `actuals`: iterable of dicts with
    forecast_year, metric, demand_basis, value (one AnnualDemandActual row
    each). Returns (pairs, refused) — refused entries carry a reason
    rather than being dropped silently (obstacle O5).
    """
    actuals_by_key: Dict[tuple, dict] = {}
    actuals_by_year_metric: Dict[tuple, List[dict]] = defaultdict(list)
    for a in actuals:
        actuals_by_key[(a['forecast_year'], a['metric'], a['demand_basis'])] = a
        actuals_by_year_metric[(a['forecast_year'], a['metric'])].append(a)

    pairs: List[ForecastActualPair] = []
    refused: List[dict] = []

    for f in figures:
        key = (f['forecast_year'], f['metric'], f['demand_basis'])
        actual = actuals_by_key.get(key)
        if actual is not None:
            pairs.append(ForecastActualPair(
                vintage_year=f['vintage_year'],
                forecast_year=f['forecast_year'],
                horizon=f['forecast_year'] - f['vintage_year'],
                metric=f['metric'],
                demand_growth_scenario=f['demand_growth_scenario'],
                poe_level=f.get('poe_level'),
                demand_basis=f['demand_basis'],
                forecast_value=f['value'],
                actual_value=actual['value'],
                unit=f['unit'],
            ))
            continue

        other_basis = actuals_by_year_metric.get((f['forecast_year'], f['metric']))
        if other_basis:
            refused.append({
                'figure': f,
                'reason': (
                    f"demand_basis mismatch: figure is '{f['demand_basis']}', "
                    f"actual(s) available on {[a['demand_basis'] for a in other_basis]}"
                ),
            })
        # else: no actual exists for this year at all yet (not scoreable
        # until the year has elapsed) — not an error, just not included.

    return pairs, refused


def _matches_group(pair: ForecastActualPair, demand_growth_scenario: str, poe_level: Optional[int]) -> bool:
    """
    Shared filter behind compute_mean_error_by_group/raw_errors_by_group.
    poe_level=50 keeps D12(a)'s existing allowance that energy figures
    (no POE axis, poe_level=None) count as the central estimate alongside
    an explicit POE50; any other requested poe_level (e.g. 10, the
    Reserve-Capacity-binding forecast) requires an exact match, since
    there's no POE-axis-absent convention to fall back to for those.
    """
    if pair.demand_growth_scenario != demand_growth_scenario:
        return False
    if poe_level == 50:
        return pair.poe_level is None or pair.poe_level == 50
    return pair.poe_level == poe_level


def compute_mean_error_by_group(
    pairs: List[ForecastActualPair],
    demand_growth_scenario: str = 'expected',
    poe_level: Optional[int] = 50,
) -> Dict[Tuple[str, int], dict]:
    """
    Generalises FR-G2-03's central-estimate lens (D12(a)) to any
    (demand_growth_scenario, poe_level) combination -- in particular the
    POE10 'binding' forecast that actually sets the Reserve Capacity
    Requirement and feeds Powermatch scenario-building
    (esoo_scenario_views.resolve_esoo_anchors), which the
    Expected/POE50-only central estimate never covers.
    """
    grouped: Dict[Tuple[str, int], List[ForecastActualPair]] = defaultdict(list)
    for p in pairs:
        if _matches_group(p, demand_growth_scenario, poe_level):
            grouped[(p.metric, p.horizon)].append(p)

    results = {}
    for key, group in grouped.items():
        errors = [p.error for p in group]
        results[key] = {
            'me': float(np.mean(errors)),
            'mae': float(np.mean(np.abs(errors))),
            'n': len(group),
            'unit': group[0].unit,
        }
    return results


def raw_errors_by_group(
    pairs: List[ForecastActualPair],
    demand_growth_scenario: str = 'expected',
    poe_level: Optional[int] = 50,
) -> Dict[Tuple[str, int], List[float]]:
    """
    Same grouping as compute_mean_error_by_group, but the raw per-pair
    signed errors rather than aggregated me/mae/n -- assess_systematic_bias
    needs the raw list to run its t-test.
    """
    grouped: Dict[Tuple[str, int], List[float]] = defaultdict(list)
    for p in pairs:
        if _matches_group(p, demand_growth_scenario, poe_level):
            grouped[(p.metric, p.horizon)].append(p.error)
    return grouped


def melt_actual_to_metric_dicts(actual) -> List[dict]:
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

    Takes any object with AnnualDemandActual's attribute shape (year,
    demand_basis, annual_energy_gwh, minimum_demand_mw, peak_demand_mw,
    peak_datetime) -- not the Django queryset itself -- so it stays
    testable without a database, matching this module's other functions.
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


def compute_central_estimate_errors(pairs: List[ForecastActualPair]) -> Dict[Tuple[str, int], dict]:
    """
    FR-G2-03, lens (a). ME (signed) and MAE per (metric, horizon), central
    estimate only (D12(a): Expected scenario, POE50-or-no-POE-axis).
    Thin wrapper over compute_mean_error_by_group's default arguments --
    kept as its own name because "central estimate" is D12(a)'s specific,
    named convention, and callers of the dashboard shouldn't need to know
    it's poe_level=50 under the hood.
    """
    return compute_mean_error_by_group(pairs, demand_growth_scenario='expected', poe_level=50)


def compute_band_calibration(
    pairs: List[ForecastActualPair], minimum_direction: Optional[str] = None,
) -> Dict[Tuple[str, int], dict]:
    """
    FR-G2-04, lens (b). For each (metric, POE level) among Expected-scenario
    figures, the realised exceedance frequency should match the nominal
    POE fraction if the band is well-calibrated.

    minimum_direction: 'above' or 'below' — REQUIRED if any 'minimum'
    figures are present, since AEMO's exceedance-direction convention for
    minimum demand is still open (spec OQ-3); this function refuses to
    guess. Peak metrics always use 'above' (actual > forecast counts as
    an exceedance), which is the standard POE convention.
    """
    grouped: Dict[Tuple[str, int], List[ForecastActualPair]] = defaultdict(list)
    for p in pairs:
        if p.demand_growth_scenario == 'expected' and p.poe_level is not None:
            grouped[(p.metric, p.poe_level)].append(p)

    results = {}
    for (metric, poe), group in grouped.items():
        if metric == 'minimum':
            if minimum_direction not in ('above', 'below'):
                raise ValueError(
                    "compute_band_calibration: 'minimum' figures present but "
                    "minimum_direction not supplied as 'above'/'below' (spec OQ-3 "
                    "is unresolved — pass it explicitly once confirmed)."
                )
            direction = minimum_direction
        else:
            direction = 'above'

        if direction == 'above':
            exceedances = sum(1 for p in group if p.actual_value > p.forecast_value)
        else:
            exceedances = sum(1 for p in group if p.actual_value < p.forecast_value)

        n = len(group)
        results[(metric, poe)] = {
            'n': n,
            'realised_frequency': exceedances / n if n else None,
            'nominal_frequency': poe / 100.0,
            'direction': direction,
        }
    return results


@dataclass
class BiasVerdict:
    verdict: str  # 'forecasts_run_high' | 'forecasts_run_low' | 'insufficient_evidence'
    n: int
    me: Optional[float]
    p_value: Optional[float]
    min_sample_size: int
    alpha: float
    notes: list = field(default_factory=list)


def assess_systematic_bias(
    errors: List[float], min_sample_size: int = DEFAULT_MIN_SAMPLE_SIZE, alpha: float = DEFAULT_ALPHA,
) -> BiasVerdict:
    """
    GR-5/FR-G2-08. Never returns a directional verdict ('forecasts_run_high'
    /'forecasts_run_low') unless both n >= min_sample_size AND a one-sample
    t-test rejects the zero-mean-error null at `alpha` — otherwise
    'insufficient_evidence', explicitly distinct from 'no bias' or 'bias'
    (the AC's literal wording).
    """
    n = len(errors)
    if n < min_sample_size:
        return BiasVerdict(
            verdict='insufficient_evidence', n=n,
            me=float(np.mean(errors)) if errors else None, p_value=None,
            min_sample_size=min_sample_size, alpha=alpha,
            notes=[f"n={n} below minimum sample size {min_sample_size}"],
        )

    me = float(np.mean(errors))
    if np.std(errors, ddof=1) == 0:
        return BiasVerdict(
            verdict='insufficient_evidence', n=n, me=me, p_value=None,
            min_sample_size=min_sample_size, alpha=alpha,
            notes=["zero variance in errors — cannot run a t-test"],
        )

    _, p_value = stats.ttest_1samp(errors, 0.0)
    p_value = float(p_value)

    if p_value < alpha:
        verdict = 'forecasts_run_high' if me > 0 else 'forecasts_run_low'
        notes = [f"p={p_value:.4f} < alpha={alpha}, n={n}"]
    else:
        verdict = 'insufficient_evidence'
        notes = [f"p={p_value:.4f} >= alpha={alpha} — mean error not distinguishable from zero at n={n}"]

    return BiasVerdict(
        verdict=verdict, n=n, me=me, p_value=p_value,
        min_sample_size=min_sample_size, alpha=alpha, notes=notes,
    )
