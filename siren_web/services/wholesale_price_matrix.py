"""
Loader for WholesalePriceMatrix — the per-year packed-array replacement
for the row-per-interval `WholesalePrice` table.

One WholesalePriceMatrix row holds a full year's half-hourly wholesale
price series as a packed float array. Like DPVGenerationMatrix, there is
no facility dimension (a single WA-wide series), so each year's row is a
flat 1-D array of length n_intervals (48 per day). Unlike DPVGenerationMatrix,
`trading_interval` here is confirmed genuine UTC (verified empirically:
price peaks at UTC hour 9-10, i.e. true AWST 17:00-18:00, the real WEM
evening peak — the same conclusion as FacilityScada.dispatch_interval, not
the legacy DPV `trading_interval` mislabelling). So this module does real
timezone conversion via `.astimezone(utc)`, mirroring
`facility_scada_matrix.py` rather than `dpv_matrix.py`.
"""
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone as dt_timezone

import numpy as np

from siren_web.models import WholesalePriceMatrix

INTERVALS_PER_DAY = 48

# Process-local cache keyed by year: (array, updated_at). Invalidated by
# comparing updated_at, so a write via set_price_values is picked up
# without restarting the process.
_cache = {}


def _intervals_in_year(year: int) -> int:
    return (date(year + 1, 1, 1) - date(year, 1, 1)).days * INTERVALS_PER_DAY


def _index_for_datetime_utc(dt_utc) -> int:
    """
    0-based index into dt_utc.year's array for a UTC-aware datetime.

    Deliberately NOT based on WholesalePrice.interval_number: that field is
    computed (by populate_wholesale_prices.py) from the raw AEMO-supplied
    trading_interval string's own .hour/.minute *before* Django converts it
    to UTC for storage -- i.e. interval_number is AWST-midnight-based,
    while the stored trading_interval is confirmed genuine UTC (see module
    docstring). Using interval_number here would silently misalign this
    UTC-indexed array by exactly 8 hours (caught via a live-data
    cross-check: aggregate stats matched but the max/min-price datetimes
    were off by exactly 8h before this fix).
    """
    day_of_year0 = (dt_utc.date() - date(dt_utc.year, 1, 1)).days
    interval_number = (dt_utc.hour * 60 + dt_utc.minute) // 30 + 1
    return day_of_year0 * INTERVALS_PER_DAY + (interval_number - 1)


def _floor_to_half_hour(dt):
    minute = 0 if dt.minute < 30 else 30
    return dt.replace(minute=minute, second=0, microsecond=0)


def load_year_array(year: int):
    """Return the 1-D half-hourly array for `year` (NaN where missing)."""
    row = WholesalePriceMatrix.objects.get(year=year)

    cached = _cache.get(year)
    if cached is not None and cached[1] == row.updated_at:
        return cached[0]

    array = row.unpack()
    _cache[year] = (array, row.updated_at)
    return array


def year_array_or_none(year: int):
    try:
        return load_year_array(year)
    except WholesalePriceMatrix.DoesNotExist:
        return None


def values_for_datetime_range(start_dt, end_dt_exclusive):
    """
    Return a 1-D float32 array of half-hourly values for [start_dt,
    end_dt_exclusive), stitching across a year boundary if needed.
    start_dt/end_dt_exclusive are converted to true UTC via .astimezone()
    -- trading_interval is confirmed genuine UTC (see module docstring).
    """
    start_utc = _floor_to_half_hour(start_dt.astimezone(dt_timezone.utc))
    end_utc = _floor_to_half_hour(end_dt_exclusive.astimezone(dt_timezone.utc))
    n = round((end_utc - start_utc).total_seconds() / 1800)
    if n <= 0:
        return np.array([], dtype='float32')

    values = np.full(n, np.nan, dtype='float32')

    first_year, last_year = start_utc.year, (end_utc - timedelta(minutes=30)).year
    for year in range(first_year, last_year + 1):
        array = year_array_or_none(year)
        if array is None:
            continue
        year_start = datetime(year, 1, 1, tzinfo=dt_timezone.utc)
        year_end = datetime(year + 1, 1, 1, tzinfo=dt_timezone.utc)
        overlap_start = max(start_utc, year_start)
        overlap_end = min(end_utc, year_end)
        if overlap_start >= overlap_end:
            continue

        src_start = round((overlap_start - year_start).total_seconds() / 1800)
        src_end = src_start + round((overlap_end - overlap_start).total_seconds() / 1800)
        dst_start = round((overlap_start - start_utc).total_seconds() / 1800)
        dst_end = dst_start + (src_end - src_start)
        values[dst_start:dst_end] = array[src_start:src_end]

    return values


def clear_range(start_dt, end_dt_exclusive):
    """
    NaN-out the half-hourly range [start_dt, end_dt_exclusive), spanning a
    year boundary if needed. No-op for a year with no matrix row.
    """
    start_utc = _floor_to_half_hour(start_dt.astimezone(dt_timezone.utc))
    end_utc = _floor_to_half_hour(end_dt_exclusive.astimezone(dt_timezone.utc))
    if end_utc <= start_utc:
        return

    first_year, last_year = start_utc.year, (end_utc - timedelta(minutes=30)).year
    for year in range(first_year, last_year + 1):
        try:
            row = WholesalePriceMatrix.objects.get(year=year)
        except WholesalePriceMatrix.DoesNotExist:
            continue

        year_start = datetime(year, 1, 1, tzinfo=dt_timezone.utc)
        year_end = datetime(year + 1, 1, 1, tzinfo=dt_timezone.utc)
        overlap_start = max(start_utc, year_start)
        overlap_end = min(end_utc, year_end)
        if overlap_start >= overlap_end:
            continue

        array = row.unpack().copy()
        s = round((overlap_start - year_start).total_seconds() / 1800)
        e = s + round((overlap_end - overlap_start).total_seconds() / 1800)
        array[s:e] = np.nan

        row.data = array.tobytes()
        row.save(update_fields=['data', 'updated_at'])
        _cache.pop(year, None)


def set_price_values(records):
    """
    Upsert half-hourly records into the packed matrix.

    records: iterable of dicts with trading_interval (any aware datetime --
    converted to true UTC here) and wholesale_price (float-like). Records
    are grouped by UTC year and each year's row is patched in place
    (existing values elsewhere in the year are left untouched), mirroring
    the ORM bulk_create/bulk_update upsert this replaces.
    """
    by_year = defaultdict(list)
    for r in records:
        dt_utc = r['trading_interval'].astimezone(dt_timezone.utc)
        by_year[dt_utc.year].append((dt_utc, r['wholesale_price']))

    for year, year_records in by_year.items():
        n = _intervals_in_year(year)
        try:
            row = WholesalePriceMatrix.objects.get(year=year)
            array = row.unpack().copy()
            if array.shape[0] != n:
                fixed = np.full(n, np.nan, dtype='float32')
                fixed[:min(n, array.shape[0])] = array[:min(n, array.shape[0])]
                array = fixed
        except WholesalePriceMatrix.DoesNotExist:
            array = np.full(n, np.nan, dtype='float32')

        for dt_utc, wholesale_price in year_records:
            idx = _index_for_datetime_utc(dt_utc)
            if 0 <= idx < n:
                array[idx] = float(wholesale_price)

        WholesalePriceMatrix.objects.update_or_create(
            year=year,
            defaults=dict(n_intervals=n, dtype='float32', data=array.tobytes()),
        )
        _cache.pop(year, None)
