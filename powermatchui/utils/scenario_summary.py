# powermatchui/utils/scenario_summary.py
"""
Key statistics for a scenario's Load (demand) trace -- pure numpy/stdlib, no
database access, so the page and any script or test share one implementation.

A trace is one calendar year at hourly or half-hourly resolution, stored in
SupplyFactorMatrix (MW per interval). The year matrix is padded with NaN out
to its widest trace, so resolution is inferred from the last valid value, not
from the array's length. Timestamps are the clock the trace was stored on
(AWST for scenarios built by the ESOO / EV builders).
"""
import calendar
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np

DURATION_POINTS = 101  # load-duration curve sampled at 0%, 1%, ... 100% of the year


class LoadTraceError(ValueError):
    """The trace can't be read as a full calendar year of hourly/half-hourly data."""


@dataclass
class LoadStats:
    year: int
    intervals_per_day: int
    n_intervals: int
    n_missing: int
    annual_energy_gwh: float
    average_mw: float
    load_factor: float
    peak_mw: float
    peak_time: datetime
    minimum_mw: float
    minimum_time: datetime
    hours_within_10pct_of_peak: float
    monthly_energy_gwh: List[float] = field(default_factory=list)
    mean_daily_profile_mw: List[float] = field(default_factory=list)
    peak_day: Optional[date] = None
    peak_day_profile_mw: List[float] = field(default_factory=list)
    duration_curve_mw: List[float] = field(default_factory=list)

    @property
    def interval_hours(self) -> float:
        return 24.0 / self.intervals_per_day

    @property
    def time_labels(self) -> List[str]:
        step = 24 * 60 // self.intervals_per_day
        return [f"{(i * step) // 60:02d}:{(i * step) % 60:02d}" for i in range(self.intervals_per_day)]


def infer_resolution(trace, year: int) -> Tuple[int, int]:
    """(valid_length, intervals_per_day) for a trace, ignoring trailing NaN padding.
    Raises LoadTraceError unless it is exactly one year at 1 or 2 intervals per hour."""
    arr = np.asarray(trace, dtype=float)
    valid = np.flatnonzero(~np.isnan(arr))
    if valid.size == 0:
        raise LoadTraceError("The trace has no values.")
    valid_len = int(valid[-1]) + 1
    days = 366 if calendar.isleap(year) else 365
    for per_day in (24, 48):
        if valid_len == days * per_day:
            return valid_len, per_day
    raise LoadTraceError(
        f"The trace has {valid_len} intervals; a {year} calendar year is {days * 24} (hourly) or {days * 48} (half-hourly)."
    )


def summarise_load_trace(trace, year: int) -> LoadStats:
    """Key statistics of one year's Load trace (MW per interval)."""
    valid_len, per_day = infer_resolution(trace, year)
    arr = np.asarray(trace, dtype=float)[:valid_len]
    hours = 24.0 / per_day
    days = valid_len // per_day
    missing = int(np.isnan(arr).sum())
    present = ~np.isnan(arr)

    energy_mwh = float(np.nansum(arr) * hours)
    average = float(np.nanmean(arr))
    peak_i = int(np.nanargmax(arr))
    min_i = int(np.nanargmin(arr))
    peak, minimum = float(arr[peak_i]), float(arr[min_i])
    start = datetime(year, 1, 1)

    by_day = arr.reshape(days, per_day)
    monthly = []
    day = 0
    for month in range(1, 13):
        n = calendar.monthrange(year, month)[1]
        monthly.append(float(np.nansum(by_day[day:day + n]) * hours / 1000.0))
        day += n

    ordered = np.sort(arr[present])[::-1]
    picks = np.round(np.linspace(0, ordered.size - 1, DURATION_POINTS)).astype(int)
    peak_day_index = peak_i // per_day

    return LoadStats(
        year=year, intervals_per_day=per_day, n_intervals=valid_len, n_missing=missing,
        annual_energy_gwh=energy_mwh / 1000.0, average_mw=average,
        load_factor=(average / peak) if peak > 0 else 0.0,
        peak_mw=peak, peak_time=start + timedelta(hours=peak_i * hours),
        minimum_mw=minimum, minimum_time=start + timedelta(hours=min_i * hours),
        hours_within_10pct_of_peak=float(np.count_nonzero(arr[present] >= 0.9 * peak) * hours) if peak > 0 else 0.0,
        monthly_energy_gwh=monthly,
        mean_daily_profile_mw=[float(v) for v in np.nanmean(by_day, axis=0)],
        peak_day=(start + timedelta(days=peak_day_index)).date(),
        peak_day_profile_mw=[float(v) for v in by_day[peak_day_index]],
        duration_curve_mw=[float(v) for v in ordered[picks]],
    )


def sum_traces(traces) -> np.ndarray:
    """Element-wise sum of several Load traces (NaN counts as 0 where another trace has data;
    stays NaN only where every trace is NaN). Traces must be the same length."""
    stack = np.vstack([np.asarray(t, dtype=float) for t in traces])
    total = np.nansum(stack, axis=0)
    total[np.all(np.isnan(stack), axis=0)] = np.nan
    return total


# ------------------------------------------------------------------ comparison

COMPARE_ROWS = [
    ('Annual energy (GWh)', 'annual_energy_gwh', '{:,.1f}'),
    ('Average load (MW)', 'average_mw', '{:,.0f}'),
    ('Peak (MW)', 'peak_mw', '{:,.0f}'),
    ('Minimum (MW)', 'minimum_mw', '{:,.0f}'),
    ('Load factor', 'load_factor', '{:.3f}'),
    ('Hours within 10% of peak', 'hours_within_10pct_of_peak', '{:,.0f}'),
]


def compare_stats(a: LoadStats, b: LoadStats) -> List[dict]:
    """Rows for a side-by-side table: label, a, b, b - a (and % change where it means something)."""
    rows = []
    for label, attr, fmt in COMPARE_ROWS:
        va, vb = getattr(a, attr), getattr(b, attr)
        rows.append({
            'label': label, 'a': fmt.format(va), 'b': fmt.format(vb),
            'delta': ('{:+' + fmt[2:-1] + '}').format(vb - va),
            'delta_pct': ((vb - va) / abs(va) * 100.0) if va else None,
            'delta_value': vb - va,
        })
    rows.append({
        'label': 'Peak time', 'a': a.peak_time.strftime('%d %b %H:%M'), 'b': b.peak_time.strftime('%d %b %H:%M'),
        'delta': '', 'delta_pct': None, 'delta_value': None,
    })
    return rows


# ------------------------------------------------------------------ provenance

_ESOO_RE = re.compile(
    r'WEM ESOO (?P<vintage>\d{4}) \((?P<scenario>\w+), POE(?P<poe>\d+)\) demand forecast for (?P<year>\d{4})')
_EV_RE = re.compile(r'CSIRO (?P<scenario>\w+) EV load \((?P<mode>\w+)\) for (?P<year>\d{4})')
_EV_NET_RE = re.compile(r'less the (?P<gwh>[\d,]+) GWh of EV load already in it')
_EV_BASE_RE = re.compile(r'Auto-built: (?P<base>.+?) base demand')


def describe_provenance(description: Optional[str], interval_minutes: Optional[int],
                        reference_year: Optional[int]) -> List[Tuple[str, str]]:
    """(label, value) pairs describing how a scenario was built, parsed from its description.
    Hand-made scenarios (no recognisable description) just get their resolution."""
    description = description or ''
    out: List[Tuple[str, str]] = []
    esoo = _ESOO_RE.search(description)
    ev = _EV_RE.search(description)
    if ev:
        out.append(('Built by', 'EV Load Scenario (FR-11)'))
        base = _EV_BASE_RE.search(description)
        if base:
            out.append(('Base demand scenario', base.group('base')))
        out.append(('EV scenario', f"{ev.group('scenario')} ({ev.group('mode')} charging), {ev.group('year')}"))
        net = _EV_NET_RE.search(description)
        out.append(('EV treatment', f"net of the {net.group('gwh')} GWh of EV load already in the ESOO base" if net
                    else "EV load added on top of the base"))
    elif esoo:
        out.append(('Built by', 'ESOO Demand Scenario (FR-G1-01)'))
        out.append(('ESOO forecast', f"WEM ESOO {esoo.group('vintage')}, {esoo.group('scenario')} scenario, "
                                     f"POE{esoo.group('poe')}, {esoo.group('year')}"))
    if reference_year:
        out.append(('Shape prior (SCADA year)', str(reference_year)))
    if interval_minutes:
        out.append(('Dispatch interval', f"{interval_minutes} minutes"))
    if description and not (esoo or ev):
        out.append(('Description', description))
    return out
