# powermatchui/utils/ev_sensitivity_comparison.py
"""
FR-12 — Low / Medium / High EV-uptake sensitivity comparison.

Pure computation over plain arrays, mirroring
powerplotui.services.ev_uptake_analysis / esoo_bias_analysis: no Django
imports, so it is unit-testable without a populated database.

Given one half-hourly base demand trace (MW) and the half-hourly EV load
trace (MW) for each CSIRO uptake scenario, this produces the per-scenario
metrics FR-12's "sensitivity comparison output" needs — energy, peak
effect, whether the system peak moves, coincident EV load at the base
peak, minimum-demand effect, load factor — plus one shared peak-day
profile slice for charting.

It never mutates or persists anything (GR-03 spirit: comparison is
analysis, not a scenario build).
"""
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, List

import numpy as np

INTERVAL_HOURS = 0.5
INTERVALS_PER_DAY = 48

# Canonical order for display — low, then medium, then high.
SCENARIO_ORDER = ('low', 'medium', 'high')


class SensitivityComparisonError(ValueError):
    pass


@dataclass
class ScenarioComparison:
    csiro_scenario: str

    ev_annual_energy_mwh: float
    base_annual_energy_mwh: float
    ev_energy_pct_of_base: float

    base_peak_mw: float
    net_peak_mw: float
    peak_delta_mw: float
    peak_delta_pct: float

    base_peak_interval: int          # 0..n-1, index of the base trace's max
    net_peak_interval: int           # index of (base+ev) max
    base_peak_time: str              # 'HH:MM'
    net_peak_time: str
    net_peak_date: str               # 'YYYY-MM-DD'
    peak_shifts: bool                # does adding EV move the system-peak interval?
    ev_at_base_peak_mw: float        # EV load in the interval the base peak falls in (coincident load)

    base_min_mw: float
    net_min_mw: float
    min_delta_mw: float

    base_load_factor: float          # mean / peak
    net_load_factor: float

    integral_check_pct: float | None = None
    notes: list = field(default_factory=list)


@dataclass
class SensitivityReport:
    forecast_year: int
    charging_mode: str
    n_intervals: int
    rows: List[ScenarioComparison]

    # One shared day for charting: the calendar day containing the highest
    # net peak across all compared scenarios (the worst-case day).
    peak_day_index: int
    peak_day_date: str
    peak_day_times: List[str]              # 48 'HH:MM' labels
    peak_day_base_mw: List[float]          # 48 values
    peak_day_net_mw: Dict[str, List[float]]  # scenario -> 48 values (base + that scenario's EV)


def _interval_time(interval_in_day: int) -> str:
    minutes = interval_in_day * 30
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _interval_date(year: int, interval: int) -> date:
    return date(year, 1, 1) + timedelta(days=interval // INTERVALS_PER_DAY)


def _load_factor(trace: np.ndarray) -> float:
    peak = float(trace.max())
    return float(trace.mean()) / peak if peak else 0.0


def compare_scenarios(
    base_trace, ev_traces: Dict[str, "np.ndarray"], forecast_year: int, charging_mode: str = 'unmanaged',
) -> SensitivityReport:
    """
    `base_trace`: half-hourly base demand (MW), length = a whole number of
    days. `ev_traces`: {csiro_scenario: half-hourly EV load (MW)} for one
    or more of 'low'/'medium'/'high', each the same length as base_trace.
    """
    base = np.asarray(base_trace, dtype=float)
    if base.ndim != 1 or base.size == 0:
        raise SensitivityComparisonError("base_trace must be a non-empty 1-D array")
    if base.size % INTERVALS_PER_DAY != 0:
        raise SensitivityComparisonError(
            f"base_trace length {base.size} is not a whole number of {INTERVALS_PER_DAY}-interval days"
        )
    if not ev_traces:
        raise SensitivityComparisonError("no EV traces supplied to compare")

    base_energy = float(base.sum() * INTERVAL_HOURS)
    base_peak_interval = int(base.argmax())
    base_peak_mw = float(base[base_peak_interval])
    base_min_mw = float(base.min())
    base_lf = _load_factor(base)

    ordered = [s for s in SCENARIO_ORDER if s in ev_traces] + \
              [s for s in ev_traces if s not in SCENARIO_ORDER]

    rows: List[ScenarioComparison] = []
    net_by_scenario: Dict[str, np.ndarray] = {}
    for scenario in ordered:
        ev = np.asarray(ev_traces[scenario], dtype=float)
        if ev.size != base.size:
            raise SensitivityComparisonError(
                f"EV trace for '{scenario}' has {ev.size} intervals but base has {base.size}"
            )
        net = base + ev
        net_by_scenario[scenario] = net

        net_peak_interval = int(net.argmax())
        net_peak_mw = float(net[net_peak_interval])
        ev_energy = float(ev.sum() * INTERVAL_HOURS)

        rows.append(ScenarioComparison(
            csiro_scenario=scenario,
            ev_annual_energy_mwh=ev_energy,
            base_annual_energy_mwh=base_energy,
            ev_energy_pct_of_base=(ev_energy / base_energy * 100.0) if base_energy else 0.0,
            base_peak_mw=base_peak_mw,
            net_peak_mw=net_peak_mw,
            peak_delta_mw=net_peak_mw - base_peak_mw,
            peak_delta_pct=((net_peak_mw - base_peak_mw) / base_peak_mw * 100.0) if base_peak_mw else 0.0,
            base_peak_interval=base_peak_interval,
            net_peak_interval=net_peak_interval,
            base_peak_time=_interval_time(base_peak_interval % INTERVALS_PER_DAY),
            net_peak_time=_interval_time(net_peak_interval % INTERVALS_PER_DAY),
            net_peak_date=_interval_date(forecast_year, net_peak_interval).isoformat(),
            peak_shifts=(net_peak_interval % INTERVALS_PER_DAY) != (base_peak_interval % INTERVALS_PER_DAY),
            ev_at_base_peak_mw=float(ev[base_peak_interval]),
            base_min_mw=base_min_mw,
            net_min_mw=float(net.min()),
            min_delta_mw=float(net.min()) - base_min_mw,
            base_load_factor=base_lf,
            net_load_factor=_load_factor(net),
        ))

    # Worst-case day: the day carrying the single highest net peak across
    # every compared scenario.
    worst_interval = max(
        (int(net.argmax()) for net in net_by_scenario.values()),
        key=lambda i: max(net[i] for net in net_by_scenario.values()),
    )
    peak_day = worst_interval // INTERVALS_PER_DAY
    day_slice = slice(peak_day * INTERVALS_PER_DAY, (peak_day + 1) * INTERVALS_PER_DAY)

    return SensitivityReport(
        forecast_year=forecast_year,
        charging_mode=charging_mode,
        n_intervals=base.size,
        rows=rows,
        peak_day_index=peak_day,
        peak_day_date=_interval_date(forecast_year, worst_interval).isoformat(),
        peak_day_times=[_interval_time(i) for i in range(INTERVALS_PER_DAY)],
        peak_day_base_mw=[float(v) for v in base[day_slice]],
        peak_day_net_mw={s: [float(v) for v in net_by_scenario[s][day_slice]] for s in ordered},
    )
