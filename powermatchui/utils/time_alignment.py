# powermatchui/utils/time_alignment.py
"""
Clock/calendar alignment for half-hourly demand traces.

FacilityScadaMatrix year arrays are UTC-indexed (index 0 = 00:00 UTC, which
is 08:00 AWST) and follow the *reference* year's weekday order. Everything
else a Powermatch scenario is combined with -- the SWIS Load and PV/wind
supply traces, and the EV charging shapes -- is on the local (AWST) clock in
the *target* year's calendar. A trace synthesised from SCADA must therefore
be moved onto the local clock and the target year's weekdays before it is
stored as a scenario Load trace, or it sits 8 hours away from every trace it
is added to (the evening peak lands at ~10:30, not ~18:30).
"""
import calendar
from typing import List, Tuple

import numpy as np

INTERVALS_PER_DAY = 48
AWST_OFFSET_INTERVALS = 16  # AWST = UTC+8 = 16 half-hours (WA has no daylight saving)


def utc_to_awst(trace) -> np.ndarray:
    """Re-index a UTC-indexed half-hourly year onto the AWST clock.

    local[j] = utc[j - 16], so the first 16 local intervals of the year come
    from the final 8 hours of the UTC year (a wrap-around, harmless for a
    synthetic shape)."""
    return np.roll(np.asarray(trace, dtype=float), AWST_OFFSET_INTERVALS)


def _year_intervals(year: int) -> int:
    return (366 if calendar.isleap(year) else 365) * INTERVALS_PER_DAY


def align_weekdays(trace, from_year: int, to_year: int) -> Tuple[np.ndarray, List[str]]:
    """Rotate a full-year trace by whole days so that its weekday pattern
    matches to_year's (day d of the result is a weekday-equivalent of day d
    of to_year). Returns (trace, notes).

    Only defined when both years have the same length and the trace covers
    the whole year; otherwise the trace is returned unchanged with a note --
    rotating a leap year against a non-leap one would smear the seasons.

    The rotation is a wrap-around: the last few days of the result (as many
    as the weekday shift, at most 6) come from the start of the reference year,
    so around that seam the pattern is a weekday out. Acceptable for a synthetic
    shape; it only ever affects the final days of December."""
    arr = np.asarray(trace, dtype=float)
    if from_year == to_year:
        return arr, []
    if _year_intervals(from_year) != _year_intervals(to_year) or arr.size != _year_intervals(to_year):
        return arr, [
            f"Weekday alignment skipped: reference year {from_year} and target year {to_year} differ in length "
            f"(or the trace is not a full year), so the trace keeps {from_year}'s weekday order."
        ]
    shift_days = (calendar.weekday(to_year, 1, 1) - calendar.weekday(from_year, 1, 1)) % 7
    return np.roll(arr, -INTERVALS_PER_DAY * shift_days), []


def align_reference_to_target(trace, reference_year: int, target_year: int) -> Tuple[np.ndarray, List[str]]:
    """UTC-indexed reference-year trace -> AWST-indexed target-year trace."""
    local = utc_to_awst(trace)
    return align_weekdays(local, reference_year, target_year)


# Stamped into every ESOO-built scenario's description once its Load trace is on
# the AWST clock in the target year's calendar. Scenarios built before that fix
# lack it (their trace is 8 h out from the traces it is combined with).
ESOO_TRACE_CLOCK_MARKER = 'AWST clock, target-year weekdays'
