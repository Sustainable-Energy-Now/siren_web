# powermatchui/utils/ev_trace_synthesis.py
"""
FR-09/FR-10 — Half-hourly EV load trace synthesis.

Unlike esoo_trace_synthesis.py (which rank-maps a duration-sorted target
onto a real reference year's chronological shape), the EV load model has
no historical SWIS reference shape to draw on — it builds the half-hourly
trace directly from AEMO's Step Change charging-profile shares
(EvChargingProfile.weekday/weekend_halfhourly_shape, D8) applied to a
CSIRO-sourced annual energy figure (D6). This is genuinely a different
construction method, not a port of the ESOO one.

Construction (FR-09, unmanaged baseline):
  1. Combine the weekday/weekend shapes of every EvChargingProfile row
     classified charging_mode='unmanaged' (D3: arrival-based charging —
     see powerplotui.services.ev_charging_profile_parser.classify_charging_mode)
     into one composite shape, weighted by each row's share_of_charging
     (D8: fixed AEMO Step Change behaviour — D1 says only CSIRO uptake
     varies, not this shape).
  2. Tile the composite weekday/weekend shape across every real calendar
     day of the target year (weekday vs weekend by actual calendar, so a
     leap year's extra day and each year's actual weekday/weekend mix are
     both handled correctly).
  3. Scale the tiled shape so its integral (MWh) equals the target annual
     energy to within FR-09's <= 0.01% near-exact tolerance -- this is a
     direct arithmetic scale-to-match, not a statistical fit.

FR-10 (managed-charging lever, D11): two ways to build the 'managed'
shape now exist, and combine_charging_type_shapes(charging_mode='managed')
gives the real one where data supports it — AEMO's own TOU/off-peak
EvChargingProfile rows (charging_mode='managed'), combined exactly like
the unmanaged case above. Where a region/vintage has no managed-mode
profile rows (or the caller wants a synthetic lever instead of the
region's own historical TOU uptake pattern), apply_managed_charging_lever()
below is a documented placeholder redistribution kernel — D11 only fixes
the objective *family* ("minimise SWIS net load"); the exact constraint
set is still FR-18 work (Open Item, Section 10 of the implementation
plan), so treat this kernel as illustrative, not FR-18-approved (obstacle
O7: unmanaged is the honest baseline, managed must stay clearly labelled
and falsifiable either way).
"""
import calendar
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import List, Optional

import numpy as np

INTERVAL_HOURS = 0.5
INTERVALS_PER_DAY = 48
ENERGY_CONSERVATION_TOLERANCE_PCT = 0.01  # FR-09: near-exact, not a statistical estimate


class TraceSynthesisError(ValueError):
    """Raised when a half-hourly EV trace cannot be honestly constructed."""


@dataclass
class ChargingTypeProfile:
    charging_type_label: str
    charging_mode: str
    share_of_charging: float
    weekday_shape: List[float]
    weekend_shape: List[float]


@dataclass
class AnnualTraceResult:
    trace: np.ndarray  # chronological half-hourly MW, length = n_intervals for the target year
    year: int
    n_intervals: int
    target_energy_mwh: float
    achieved_energy_mwh: float
    integral_check_pct: float
    notes: list = field(default_factory=list)


def _normalise_shape(shape: List[float], label: str) -> np.ndarray:
    arr = np.asarray(shape, dtype=float)
    if arr.size != INTERVALS_PER_DAY:
        raise TraceSynthesisError(f"{label} must have {INTERVALS_PER_DAY} half-hourly values, got {arr.size}")
    total = arr.sum()
    if total <= 0:
        raise TraceSynthesisError(f"{label} sums to {total} — cannot normalise a non-positive shape")
    return arr / total


def combine_charging_type_shapes(profiles: List[ChargingTypeProfile], charging_mode: str):
    """
    FR-09 step 1 (or the real-data half of FR-10). Combine the
    weekday/weekend shapes of every profile matching `charging_mode`
    ('unmanaged' or 'managed') into one composite daily shape, weighted
    by each row's share_of_charging. Shares are re-normalised to sum to
    1 across the matching profiles actually supplied (so a caller can
    build a composite from a subset of charging types, e.g. a region
    missing one type's data, without silently understating total
    charging) -- this also means a charging_type with no static shape
    (e.g. AEMO's "TOU Dynamic Charging", which AEMO itself documents as
    having no static time-of-day profile) is simply absent from the
    composite rather than zero-filled, which understates that
    charging_mode's true total share; callers combining 'managed' should
    treat the result as a lower bound on real managed-charging uptake,
    not the complete picture, until FR-18 defines how to represent a
    dynamically-computed (non-static) charging type here.
    """
    matching = [p for p in profiles if p.charging_mode == charging_mode]
    if not matching:
        raise TraceSynthesisError(f"No charging-type profiles with charging_mode='{charging_mode}' supplied")

    total_share = sum(p.share_of_charging for p in matching)
    if total_share <= 0:
        raise TraceSynthesisError(
            f"charging_mode='{charging_mode}' shares sum to {total_share} — cannot weight a composite shape"
        )

    weekday_composite = np.zeros(INTERVALS_PER_DAY)
    weekend_composite = np.zeros(INTERVALS_PER_DAY)
    for p in matching:
        weight = p.share_of_charging / total_share
        weekday_composite += weight * _normalise_shape(p.weekday_shape, f"{p.charging_type_label} weekday_shape")
        weekend_composite += weight * _normalise_shape(p.weekend_shape, f"{p.charging_type_label} weekend_shape")

    return weekday_composite, weekend_composite


def _expected_intervals(year: int) -> int:
    return (366 if calendar.isleap(year) else 365) * INTERVALS_PER_DAY


def shape_annual_energy_to_halfhourly(
    annual_energy_mwh: float, weekday_shape: np.ndarray, weekend_shape: np.ndarray, year: int,
) -> AnnualTraceResult:
    """
    FR-09 steps 2-3. Tile the composite weekday/weekend shape across
    every real calendar day of `year`, then scale to match
    annual_energy_mwh's integral to within ENERGY_CONSERVATION_TOLERANCE_PCT.
    """
    first_day = date(year, 1, 1)
    n_days = 366 if calendar.isleap(year) else 365

    daily_shapes = np.empty((n_days, INTERVALS_PER_DAY))
    for i in range(n_days):
        is_weekend = (first_day + timedelta(days=i)).weekday() >= 5  # Sat=5, Sun=6
        daily_shapes[i] = weekend_shape if is_weekend else weekday_shape

    # Each day's INTERVALS_PER_DAY fractions sum to 1 (a share of THAT
    # day's energy); spreading annual_energy_mwh evenly across n_days
    # before applying the intra-day shape is the honest reading of D6/D8 --
    # this pipeline has no sub-annual (e.g. seasonal) shape signal to
    # apportion energy unevenly across the year, so daily totals are equal.
    energy_per_day_mwh = annual_energy_mwh / n_days
    # trace value (MW) for a half-hourly interval carrying `share` of one
    # day's energy_per_day_mwh: MW = (share * energy_per_day_mwh) / INTERVAL_HOURS
    trace = (daily_shapes.flatten() * energy_per_day_mwh) / INTERVAL_HOURS

    achieved_energy_mwh = float(trace.sum() * INTERVAL_HOURS)
    integral_check_pct = (
        abs(achieved_energy_mwh - annual_energy_mwh) / abs(annual_energy_mwh) * 100.0
        if annual_energy_mwh else 0.0
    )

    notes = []
    if integral_check_pct > ENERGY_CONSERVATION_TOLERANCE_PCT:
        notes.append(
            f"Integral check {integral_check_pct:.6f}% exceeds FR-09's "
            f"{ENERGY_CONSERVATION_TOLERANCE_PCT}% near-exact tolerance — investigate before trusting this trace."
        )

    return AnnualTraceResult(
        trace=trace,
        year=year,
        n_intervals=trace.size,
        target_energy_mwh=annual_energy_mwh,
        achieved_energy_mwh=achieved_energy_mwh,
        integral_check_pct=integral_check_pct,
        notes=notes,
    )


def require_energy_conserved(result: AnnualTraceResult) -> AnnualTraceResult:
    """Raise TraceSynthesisError if `result` failed FR-09's near-exact
    integral check; otherwise return it unchanged."""
    if result.integral_check_pct > ENERGY_CONSERVATION_TOLERANCE_PCT:
        raise TraceSynthesisError(
            f"EV load trace for {result.year} failed FR-09's energy-conservation check: "
            f"{result.integral_check_pct:.6f}% > {ENERGY_CONSERVATION_TOLERANCE_PCT}%"
        )
    return result


def apply_managed_charging_lever(
    trace: np.ndarray, offpeak_start_interval: int = 0, offpeak_end_interval: int = 14,
    shift_fraction: float = 0.5,
) -> np.ndarray:
    """
    FR-10 placeholder managed-charging redistribution (D11 objective
    family only — see module docstring; FR-18 still owes the exact
    constraint set). Shifts `shift_fraction` of the energy in every
    half-hour OUTSIDE [offpeak_start_interval, offpeak_end_interval) into
    that off-peak window, per calendar day, exactly conserving each day's
    total energy (D11: redistribution, not creation/destruction of load).

    Default off-peak window (intervals 0-14 = 00:00-07:00) is a simple,
    documented placeholder for "overnight", not an AEMO-sourced ToU
    window -- callers driving a real managed-charging scenario should
    override it once FR-18 fixes the actual constraint set.
    """
    if trace.size % INTERVALS_PER_DAY != 0:
        raise TraceSynthesisError(
            f"apply_managed_charging_lever expects a whole number of days "
            f"({INTERVALS_PER_DAY} intervals each); got {trace.size} intervals"
        )
    if not (0 <= offpeak_start_interval < offpeak_end_interval <= INTERVALS_PER_DAY):
        raise TraceSynthesisError("Invalid off-peak window bounds")
    if not (0.0 <= shift_fraction <= 1.0):
        raise TraceSynthesisError("shift_fraction must be between 0 and 1")

    daily = trace.reshape(-1, INTERVALS_PER_DAY).copy()
    offpeak_mask = np.zeros(INTERVALS_PER_DAY, dtype=bool)
    offpeak_mask[offpeak_start_interval:offpeak_end_interval] = True
    onpeak_mask = ~offpeak_mask
    n_offpeak = int(offpeak_mask.sum())

    onpeak_energy = daily[:, onpeak_mask].sum(axis=1)  # per-day, MW-summed (energy up to the INTERVAL_HOURS factor)
    shifted_energy = onpeak_energy * shift_fraction

    daily[:, onpeak_mask] *= (1.0 - shift_fraction)
    daily[:, offpeak_mask] += (shifted_energy / n_offpeak)[:, None]

    return daily.flatten()
