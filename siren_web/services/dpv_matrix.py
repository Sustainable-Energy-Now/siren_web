"""
Loader for DPVGenerationMatrix — the per-year packed-array replacement for
the row-per-interval `dpv_generation` table.

One DPVGenerationMatrix row holds a full year's half-hourly DPV (rooftop
solar) generation estimates as a packed float array. Unlike
SupplyFactorMatrix (facility x hour), there is no facility dimension here —
DPV is a single WA-wide series — so each year's row is just a flat
1-D array of length n_intervals (48 per day). Missing intervals are NaN.
"""
from collections import defaultdict
from datetime import date, datetime, timedelta

import numpy as np

from siren_web.models import DPVGenerationMatrix

INTERVALS_PER_DAY = 48

# Process-local cache keyed by year: (array, updated_at). Invalidated by
# comparing updated_at, so a write via set_interval_values is picked up
# without restarting the process.
_cache = {}


def _intervals_in_year(year: int) -> int:
    return (date(year + 1, 1, 1) - date(year, 1, 1)).days * INTERVALS_PER_DAY


def _index_for_date(trading_date, interval_number: int) -> int:
    """0-based index into trading_date's year array for interval_number (1-48)."""
    day_of_year0 = (trading_date - date(trading_date.year, 1, 1)).days
    return day_of_year0 * INTERVALS_PER_DAY + (interval_number - 1)


def load_year_array(year: int):
    """Return the 1-D half-hourly array for `year` (NaN where missing)."""
    row = DPVGenerationMatrix.objects.get(year=year)

    cached = _cache.get(year)
    if cached is not None and cached[1] == row.updated_at:
        return cached[0]

    array = row.unpack()
    _cache[year] = (array, row.updated_at)
    return array


def year_array_or_none(year: int):
    try:
        return load_year_array(year)
    except DPVGenerationMatrix.DoesNotExist:
        return None


def values_for_date_range(start_date, end_date_exclusive):
    """
    Return a 1-D float32 array of half-hourly values for the calendar-date
    range [start_date, end_date_exclusive) — length
    (end_date_exclusive - start_date).days * 48, chronologically ordered.
    Years with no matrix row, or dates past a year's stored width, come
    back as NaN.
    """
    if end_date_exclusive <= start_date:
        return np.array([], dtype='float32')

    chunks = []
    d = start_date
    while d < end_date_exclusive:
        year_end = date(d.year + 1, 1, 1)
        chunk_end = min(end_date_exclusive, year_end)
        n_days = (chunk_end - d).days
        n_values = n_days * INTERVALS_PER_DAY

        array = year_array_or_none(d.year)
        if array is None:
            chunks.append(np.full(n_values, np.nan, dtype='float32'))
        else:
            start_idx = _index_for_date(d, 1)
            end_idx = start_idx + n_values
            chunk = np.full(n_values, np.nan, dtype='float32')
            src = array[max(start_idx, 0):min(end_idx, array.shape[0])]
            chunk[:src.shape[0]] = src
            chunks.append(chunk)

        d = chunk_end

    return np.concatenate(chunks)


def values_for_datetime_range(start_dt, end_dt_exclusive):
    """
    Return a 1-D float32 array of half-hourly values for the range
    [start_dt, end_dt_exclusive), read by wall-clock time.

    tzinfo on the arguments is ignored -- only the local wall-clock digits
    matter. This matches the only reliable convention in this data: trading_date
    / interval_number are unambiguous AWST trading-period labels, but the
    legacy dpv_generation.trading_interval field stores those same AWST
    wall-clock digits mislabeled with a UTC tzinfo, and callers throughout
    this codebase build their date-range boundaries the same wall-clock way
    (e.g. `timezone.make_aware(datetime(year, month, 1, ...))` under
    settings.TIME_ZONE='UTC'). Actually converting an aware argument to AWST
    here (via .astimezone) would silently shift such boundaries by hours.
    """
    start_dt = _floor_to_half_hour(start_dt.replace(tzinfo=None))
    end_dt_exclusive = _floor_to_half_hour(end_dt_exclusive.replace(tzinfo=None))
    n = round((end_dt_exclusive - start_dt).total_seconds() / 1800)
    if n <= 0:
        return np.array([], dtype='float32')

    values = np.full(n, np.nan, dtype='float32')

    first_year, last_year = start_dt.year, (end_dt_exclusive - timedelta(minutes=30)).year
    for year in range(first_year, last_year + 1):
        array = year_array_or_none(year)
        if array is None:
            continue
        year_start = datetime(year, 1, 1)
        year_end = datetime(year + 1, 1, 1)
        overlap_start = max(start_dt, year_start)
        overlap_end = min(end_dt_exclusive, year_end)
        if overlap_start >= overlap_end:
            continue

        src_start = round((overlap_start - year_start).total_seconds() / 1800)
        src_end = src_start + round((overlap_end - overlap_start).total_seconds() / 1800)
        dst_start = round((overlap_start - start_dt).total_seconds() / 1800)
        dst_end = dst_start + (src_end - src_start)
        values[dst_start:dst_end] = array[src_start:src_end]

    return values


def _floor_to_half_hour(dt):
    minute = 0 if dt.minute < 30 else 30
    return dt.replace(minute=minute, second=0, microsecond=0)


def interval_coverage(start_dt, end_dt_exclusive):
    """Return (non_nan_count, total_count) for a datetime range — for coverage checks."""
    values = values_for_datetime_range(start_dt, end_dt_exclusive)
    return int(np.count_nonzero(~np.isnan(values))), values.shape[0]


def has_data_on(trading_date) -> bool:
    """Whether any interval on trading_date has a non-NaN value."""
    array = year_array_or_none(trading_date.year)
    if array is None:
        return False
    start = _index_for_date(trading_date, 1)
    end = start + INTERVALS_PER_DAY
    day = array[max(start, 0):min(end, array.shape[0])]
    return bool(day.size) and not np.all(np.isnan(day))


def latest_trading_date():
    """Return the most recent trading_date with a non-NaN value, or None."""
    for row_year in DPVGenerationMatrix.objects.order_by('-year').values_list('year', flat=True):
        array = load_year_array(row_year)
        valid = np.flatnonzero(~np.isnan(array))
        if valid.size:
            last_idx = int(valid[-1])
            return date(row_year, 1, 1) + timedelta(days=last_idx // INTERVALS_PER_DAY)
    return None


def set_interval_values(records):
    """
    Upsert half-hourly records into the packed matrix.

    records: iterable of dicts with trading_date, interval_number (1-48)
    and estimated_generation (float-like). Records are grouped by year and
    each year's row is patched in place (existing values elsewhere in the
    year are left untouched), mirroring the raw-SQL
    "ON DUPLICATE KEY UPDATE" upsert this replaces.
    """
    by_year = defaultdict(list)
    for r in records:
        by_year[r['trading_date'].year].append(r)

    for year, year_records in by_year.items():
        n = _intervals_in_year(year)
        try:
            row = DPVGenerationMatrix.objects.get(year=year)
            array = row.unpack().copy()
            if array.shape[0] != n:
                fixed = np.full(n, np.nan, dtype='float32')
                fixed[:min(n, array.shape[0])] = array[:min(n, array.shape[0])]
                array = fixed
        except DPVGenerationMatrix.DoesNotExist:
            array = np.full(n, np.nan, dtype='float32')

        for r in year_records:
            idx = _index_for_date(r['trading_date'], r['interval_number'])
            if 0 <= idx < n:
                array[idx] = float(r['estimated_generation'])

        DPVGenerationMatrix.objects.update_or_create(
            year=year,
            defaults=dict(n_intervals=n, dtype='float32', data=array.tobytes()),
        )
        _cache.pop(year, None)
