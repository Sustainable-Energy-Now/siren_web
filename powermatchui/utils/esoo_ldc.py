# powermatchui/utils/esoo_ldc.py
"""
FR-G1-02 — Load duration curve (LDC) construction from ESOO anchors.

An LDC sorts demand high-to-low against the fraction of time exceeded:
the peak sits at ~0% duration, the minimum at ~100%, and the area under
the curve equals total annual energy (D8). Obstacle O8 notes that two
numbers (energy, peak) don't fix a full trace — this module resolves that
by taking the *shape* from a real reference year (D10's "reference-year
shape prior") and applying a single peakiness adjustment so the result
hits all three published anchors (peak, minimum, energy) exactly, rather
than assuming an arbitrary parametric curve family with no empirical
basis.

Method: normalise the reference year's own duration curve to [0, 1]
(D8's peak-normalised form), then raise it to a shape exponent gamma
solved so the rescaled curve's mean lands exactly on the energy-implied
average. gamma=1 reproduces the reference year's own relative shape
unchanged; gamma>1 pulls the curve toward a peakier (more front-loaded)
shape; gamma<1 flattens it. Where gamma ends up far from 1, that itself
is a useful diagnostic: it means the reference year's shape doesn't
naturally fit the target anchors, which FR-G1-04's non-stationarity
logging (D10) should surface.

This module only constructs the LDC; it does not decide whether the
result is acceptable — that's FR-G1-05 (esoo_reconciliation.py).
"""
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from scipy.optimize import brentq


class LDCConstructionError(ValueError):
    """Raised when the requested anchors are physically inconsistent
    (e.g. average implied by energy isn't between minimum and peak) or a
    reference shape can't produce a valid duration curve."""


@dataclass
class LDCFit:
    """Result of fitting a reference shape to target anchors."""
    absolute: np.ndarray            # duration-sorted MW values, index 0 = peak
    normalised: np.ndarray          # same curve peak-normalised to [0, 1]
    gamma: float                    # solved shape exponent
    target_peak: float
    target_minimum: float
    target_energy_mwh: float
    achieved_energy_mwh: float      # energy actually implied by `absolute`
    interval_hours: float
    reference_year: Optional[str] = None
    notes: list = field(default_factory=list)


def compute_duration_curve(values) -> np.ndarray:
    """Sort a chronological (or any-order) series into a duration curve:
    descending order, peak first, minimum last."""
    arr = np.asarray(values, dtype=float)
    arr = arr[~np.isnan(arr)]
    if arr.size == 0:
        raise LDCConstructionError("Cannot build a duration curve from an empty series")
    return np.sort(arr)[::-1]


def peak_normalise(ldc: np.ndarray, minimum: Optional[float] = None) -> np.ndarray:
    """Rescale a duration-sorted curve to [0, 1]: 1.0 at the peak, 0.0 at
    the minimum (D8's peak-normalised form)."""
    peak = ldc[0]
    floor = ldc[-1] if minimum is None else minimum
    span = peak - floor
    if span <= 0:
        raise LDCConstructionError(f"Cannot normalise a curve with peak ({peak}) <= minimum ({floor})")
    return (ldc - floor) / span


def _mean_of_power(normalised: np.ndarray, gamma: float) -> float:
    # normalised is in [0, 1]; 0**negative is undefined, but gamma is
    # bounded away from <=0 by the bracket used in fit_ldc_to_anchors.
    return float(np.mean(np.power(normalised, gamma)))


def fit_ldc_to_anchors(
    reference_shape,
    target_peak: float,
    target_minimum: float,
    target_energy_mwh: float,
    interval_hours: float = 0.5,
    reference_year: Optional[str] = None,
    gamma_bracket=(1e-4, 1e4),
) -> LDCFit:
    """
    Construct a target LDC that exactly reproduces target_peak,
    target_minimum, and target_energy_mwh, using `reference_shape`'s own
    duration-curve shape (a chronological or unsorted array of MW values
    for one reference year, e.g. from FacilityScada or the AEMO Demand
    Traces workbook) as the shape prior (D10).

    Raises LDCConstructionError if the anchors are inconsistent (the
    energy-implied average must lie strictly between target_minimum and
    target_peak — obstacle O8's "two numbers don't fix a trace" problem
    resolved by requiring three consistent anchors) or if no gamma in
    `gamma_bracket` reproduces the target average.
    """
    if target_peak <= target_minimum:
        raise LDCConstructionError(
            f"target_peak ({target_peak}) must exceed target_minimum ({target_minimum})"
        )

    reference_ldc = compute_duration_curve(reference_shape)
    normalised_ref = peak_normalise(reference_ldc)
    n = normalised_ref.size

    target_average = target_energy_mwh / (n * interval_hours)
    if not (target_minimum < target_average < target_peak):
        raise LDCConstructionError(
            f"Energy-implied average ({target_average:.2f}) must lie strictly between "
            f"target_minimum ({target_minimum}) and target_peak ({target_peak}); "
            f"the three anchors are inconsistent with each other."
        )

    # mean(normalised**gamma) decreases monotonically from ~1 (gamma->0,
    # curve flattens toward the peak) to 0 (gamma->inf, only the peak
    # point contributes) — so this fraction is what gamma must hit.
    target_fraction = (target_average - target_minimum) / (target_peak - target_minimum)

    lo, hi = gamma_bracket
    f_lo = _mean_of_power(normalised_ref, lo) - target_fraction
    f_hi = _mean_of_power(normalised_ref, hi) - target_fraction
    if f_lo * f_hi > 0:
        raise LDCConstructionError(
            f"No gamma in {gamma_bracket} reproduces the target average fraction "
            f"({target_fraction:.4f}) from this reference shape — its own shape may be "
            f"too extreme (e.g. near-flat or near-spike) for these anchors."
        )

    gamma = brentq(lambda g: _mean_of_power(normalised_ref, g) - target_fraction, lo, hi)

    normalised_out = np.power(normalised_ref, gamma)
    absolute = target_minimum + (target_peak - target_minimum) * normalised_out
    achieved_energy = float(np.sum(absolute) * interval_hours)

    notes = []
    if not (0.5 <= gamma <= 2.0):
        notes.append(
            f"gamma={gamma:.3f} is far from 1.0 — the reference year's shape doesn't "
            f"naturally fit these anchors; treat the reconstructed shape with caution "
            f"(D10 non-stationarity)."
        )

    return LDCFit(
        absolute=absolute,
        normalised=normalised_out,
        gamma=gamma,
        target_peak=target_peak,
        target_minimum=target_minimum,
        target_energy_mwh=target_energy_mwh,
        achieved_energy_mwh=achieved_energy,
        interval_hours=interval_hours,
        reference_year=reference_year,
        notes=notes,
    )
