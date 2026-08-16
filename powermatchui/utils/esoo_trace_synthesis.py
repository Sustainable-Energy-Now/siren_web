# powermatchui/utils/esoo_trace_synthesis.py
"""
FR-G1-03/04 — Chronological trace synthesis.

Converts a target LDC (esoo_ldc.py's fit_ldc_to_anchors output — a
duration-sorted curve with no calendar information) into a chronological
half-hourly series Powermatch can actually dispatch against, by
rank-mapping: whichever calendar half-hour held rank i (i.e. the i-th
highest value) in the reference year's own chronological shape gets
assigned the target LDC's rank-i value. This is an exact permutation, so
re-sorting the synthesised trace reproduces the target LDC exactly (not
just "within tolerance" — FR-G1-03's AC is satisfied to floating-point
precision by construction), while every calendar slot's *relative*
position (peak day, overnight trough, shoulder-season shape) is carried
over unchanged from the reference year.

FR-G1-04 requires defaulting to a recent-actual-year shape prior, exposing
the reference-year choice, and logging shape non-stationarity as a
documented limitation (D10) — see select_reference_year() and
TraceSynthesisResult.notes below.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Sequence

import numpy as np

from powermatchui.utils.esoo_ldc import LDCConstructionError


@dataclass
class TraceSynthesisResult:
    trace: np.ndarray               # chronological half-hourly series, same length/order as reference_shape
    reference_year: str
    horizon_aware: bool
    max_resort_deviation: float     # |sorted(trace) - target_ldc|, should be ~0 (float rounding only)
    notes: list = field(default_factory=list)


def synthesize_chronological_trace(target_ldc, reference_shape, reference_year: Optional[str] = None) -> TraceSynthesisResult:
    """
    Rank-map `target_ldc` (duration-sorted, from esoo_ldc.fit_ldc_to_anchors)
    onto the chronological ordering of `reference_shape` (a real reference
    year's half-hourly values, same length, any order).
    """
    target = np.asarray(target_ldc, dtype=float)
    reference = np.asarray(reference_shape, dtype=float)

    if target.size != reference.size:
        raise LDCConstructionError(
            f"target_ldc ({target.size} points) and reference_shape ({reference.size} points) "
            f"must be the same length — synthesis does not resample between calendars."
        )
    if not np.all(np.diff(target) <= 0):
        raise LDCConstructionError("target_ldc must already be duration-sorted (descending)")

    # rank[k] = position in the sort-order (0 = highest) of reference[k].
    # argsort ascending, reversed, gives indices from highest to lowest;
    # inverting that permutation gives each index's rank directly.
    order_desc = np.argsort(reference)[::-1]
    rank = np.empty_like(order_desc)
    rank[order_desc] = np.arange(reference.size)

    trace = target[rank]

    resorted = np.sort(trace)[::-1]
    max_deviation = float(np.max(np.abs(resorted - target)))

    notes = []
    if max_deviation > 1e-6:
        notes.append(
            f"Re-sorted trace deviates from target_ldc by up to {max_deviation:.6g} — "
            f"unexpected for a pure rank permutation; investigate before trusting this trace."
        )

    return TraceSynthesisResult(
        trace=trace,
        reference_year=reference_year or "unspecified",
        horizon_aware=False,
        max_resort_deviation=max_deviation,
        notes=notes,
    )


def select_reference_year(available_years: Sequence[str], forecast_year: Optional[int] = None,
                           base_year: Optional[int] = None, horizon_aware: bool = False) -> str:
    """
    D10: choose which reference year's shape to use as the prior.

    Default (horizon_aware=False): the single most-recent available year
    — "recent-actual-year shape prior" per FR-G1-04's default.

    horizon_aware=True: cycles deterministically through
    `available_years` (sorted) based on (forecast_year - base_year), so
    different forecast years in a multi-year outlook draw different
    reference-year shapes rather than all reusing the same one. This is a
    simple, documented placeholder policy, not a claim that it's the
    statistically optimal choice — D10 only requires that a horizon-aware
    *option* exist, not a specific algorithm; refine this once G2's bias
    analysis has evidence on which reference-year choice performs best.
    """
    if not available_years:
        raise LDCConstructionError("No available reference years to choose from")

    ordered = sorted(available_years)
    if not horizon_aware or forecast_year is None or base_year is None:
        return ordered[-1]

    offset = (forecast_year - base_year) % len(ordered)
    return ordered[offset]
