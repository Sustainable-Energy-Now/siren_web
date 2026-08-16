# powermatchui/utils/esoo_reconciliation.py
"""
FR-G1-05 — Acceptance reconciliation.

esoo_ldc.fit_ldc_to_anchors() already solves for an exact reproduction of
all three anchors (peak, minimum, energy) by construction, and
esoo_trace_synthesis's rank-mapping is an exact permutation that preserves
them — so for this construction method, obstacle O8's "energy and peak
anchors compete" scenario (OQ-5) doesn't actually arise: there is no
trade-off to resolve, because the single shape exponent (gamma) is solved
to satisfy all three simultaneously. Reconciliation still matters as a
defensive final check on the artefact that actually gets handed to
Powermatch (catching numerical drift, a future alternative construction
method that isn't exact, or a caller bypassing esoo_ldc entirely with a
hand-built trace) and as the formal, loggable "reconciliation report" this
requirement's AC calls for.

DEFAULT_TOLERANCE_PCT resolves OQ-5's "what tolerance is acceptable"
question as an explicit, overridable parameter rather than an implicit
assumption: 0.5% gives headroom for real floating-point/representation
noise while still catching genuine problems, given the construction
method above is normally exact to ~1e-6.
"""
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

DEFAULT_TOLERANCE_PCT = 0.5


class TraceRejectedError(ValueError):
    """Raised by require_reconciled() when a trace fails reconciliation —
    the 'out-of-tolerance traces are blocked' half of FR-G1-05's AC."""


@dataclass
class ReconciliationReport:
    passed: bool
    tolerance_pct: float
    target_peak: float
    achieved_peak: float
    target_minimum: float
    achieved_minimum: float
    target_energy_mwh: float
    achieved_energy_mwh: float
    notes: list = field(default_factory=list)

    @property
    def peak_error_pct(self) -> float:
        return _pct_error(self.achieved_peak, self.target_peak)

    @property
    def minimum_error_pct(self) -> float:
        return _pct_error(self.achieved_minimum, self.target_minimum)

    @property
    def energy_error_pct(self) -> float:
        return _pct_error(self.achieved_energy_mwh, self.target_energy_mwh)


def _pct_error(achieved: float, target: float) -> float:
    if target == 0:
        return 0.0 if achieved == 0 else float('inf')
    return abs(achieved - target) / abs(target) * 100.0


def reconcile_trace(
    trace,
    target_peak: float,
    target_minimum: float,
    target_energy_mwh: float,
    interval_hours: float = 0.5,
    tolerance_pct: float = DEFAULT_TOLERANCE_PCT,
) -> ReconciliationReport:
    """
    Compare a synthesised chronological trace against its three source
    anchors and report whether it's within tolerance_pct of each.
    """
    arr = np.asarray(trace, dtype=float)
    achieved_peak = float(arr.max())
    achieved_minimum = float(arr.min())
    achieved_energy = float(arr.sum() * interval_hours)

    report = ReconciliationReport(
        passed=True,  # provisional; finalised below
        tolerance_pct=tolerance_pct,
        target_peak=target_peak,
        achieved_peak=achieved_peak,
        target_minimum=target_minimum,
        achieved_minimum=achieved_minimum,
        target_energy_mwh=target_energy_mwh,
        achieved_energy_mwh=achieved_energy,
    )

    checks = [
        ('peak', report.peak_error_pct),
        ('minimum', report.minimum_error_pct),
        ('energy', report.energy_error_pct),
    ]
    failed = [(name, err) for name, err in checks if err > tolerance_pct]
    report.passed = not failed
    if failed:
        report.notes = [
            f"{name} error {err:.4f}% exceeds tolerance {tolerance_pct}%"
            for name, err in failed
        ]
    return report


def require_reconciled(report: ReconciliationReport) -> ReconciliationReport:
    """Raise TraceRejectedError if `report` didn't pass; otherwise return
    it unchanged, so this can be used inline: trace = require_reconciled(reconcile_trace(...))."""
    if not report.passed:
        raise TraceRejectedError(
            f"Trace rejected — anchors outside {report.tolerance_pct}% tolerance: "
            + "; ".join(report.notes)
        )
    return report
