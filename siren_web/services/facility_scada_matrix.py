"""
Loader for FacilityScadaMatrix — the per-year (facility x half-hourly
interval) replacement for the row-per-(facility, interval) `facility_scada`
table.

One FacilityScadaMatrix row holds every facility's half-hourly SCADA energy
trace for a year as a packed float array (facility_ids gives row order).
Unlike DPVGenerationMatrix, this needs a facility dimension (like
SupplyFactorMatrix); unlike SupplyFactorMatrix, it's always half-hourly, not
hourly, and its interval indexing is UTC-based -- `dispatch_interval` is
confirmed to be stored as genuine UTC (unlike the legacy DPV
`trading_interval` field, which was found to be mislabelled), so range
queries here do real timezone conversion via `.astimezone(utc)` rather than
the wall-clock-digit convention DPV needed.
"""
from calendar import monthrange
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone as dt_timezone

import numpy as np

from siren_web.models import FacilityScadaMatrix

INTERVALS_PER_DAY = 48

# Process-local cache keyed by year: (facility_ids, matrix, updated_at).
# Invalidated by comparing updated_at, so a write via set_scada_values is
# picked up without restarting the process.
_cache = {}


def _intervals_in_year(year: int) -> int:
    return (date(year + 1, 1, 1) - date(year, 1, 1)).days * INTERVALS_PER_DAY


def _index_for_date(trading_date, interval_number: int) -> int:
    """0-based index into trading_date's (UTC) year array for interval_number (1-48)."""
    day_of_year0 = (trading_date - date(trading_date.year, 1, 1)).days
    return day_of_year0 * INTERVALS_PER_DAY + (interval_number - 1)


def _index_for_datetime_utc(dt_utc) -> int:
    """0-based index into dt_utc.year's array for a UTC-aware datetime."""
    interval_number = (dt_utc.hour * 60 + dt_utc.minute) // 30 + 1
    return _index_for_date(dt_utc.date(), interval_number)


def _floor_to_half_hour(dt):
    minute = 0 if dt.minute < 30 else 30
    return dt.replace(minute=minute, second=0, microsecond=0)


def load_year_matrix(year: int):
    """
    Return (facility_ids, matrix) for a year, where matrix has shape
    (len(facility_ids), n_intervals) and matrix[i, :] is facility_ids[i]'s
    half-hourly energy trace (MWh). Missing values are NaN.
    """
    row = FacilityScadaMatrix.objects.get(year=year)

    cached = _cache.get(year)
    if cached is not None and cached[2] == row.updated_at:
        return cached[0], cached[1]

    facility_ids, matrix = row.unpack()
    _cache[year] = (facility_ids, matrix, row.updated_at)
    return facility_ids, matrix


def earliest_dispatch_interval():
    """Return the earliest UTC datetime with any non-NaN cell, or None."""
    for row_year in FacilityScadaMatrix.objects.order_by('year').values_list('year', flat=True):
        _, matrix = load_year_matrix(row_year)
        with np.errstate(invalid='ignore'):
            has_data = ~np.all(np.isnan(matrix), axis=0)
        valid = np.flatnonzero(has_data)
        if valid.size:
            return datetime(row_year, 1, 1, tzinfo=dt_timezone.utc) + timedelta(minutes=30 * int(valid[0]))
    return None


def latest_dispatch_interval():
    """Return the latest UTC datetime with any non-NaN cell, or None."""
    for row_year in FacilityScadaMatrix.objects.order_by('-year').values_list('year', flat=True):
        _, matrix = load_year_matrix(row_year)
        with np.errstate(invalid='ignore'):
            has_data = ~np.all(np.isnan(matrix), axis=0)
        valid = np.flatnonzero(has_data)
        if valid.size:
            return datetime(row_year, 1, 1, tzinfo=dt_timezone.utc) + timedelta(minutes=30 * int(valid[-1]))
    return None


def year_present_mask(year: int):
    """Boolean mask, shape (n_intervals,): whether ANY facility has data for that interval."""
    _, matrix = load_year_matrix(year)
    if matrix.shape[0] == 0:
        return np.zeros(matrix.shape[1], dtype=bool)
    with np.errstate(invalid='ignore'):
        return ~np.all(np.isnan(matrix), axis=0)


def facility_row_index(facility_ids):
    """Map facility id -> row index into the matrix returned by load_year_matrix."""
    return {fid: i for i, fid in enumerate(facility_ids)}


def facility_trace(year: int, facility_id: int):
    """Return the 1-D half-hourly trace (MWh) for a single facility, or None if absent."""
    try:
        facility_ids, matrix = load_year_matrix(year)
    except FacilityScadaMatrix.DoesNotExist:
        return None
    idx = facility_row_index(facility_ids)
    i = idx.get(facility_id)
    if i is None:
        return None
    return matrix[i, :]


def facility_has_trace(year: int, facility_id: int) -> bool:
    """Whether facility_id has a row in year's matrix at all (no NaN check)."""
    try:
        facility_ids, _ = load_year_matrix(year)
    except FacilityScadaMatrix.DoesNotExist:
        return False
    return facility_id in facility_ids


def facilities_trace_sum(year: int, facility_ids_wanted):
    """
    Return the elementwise sum across the given facility ids' traces
    (shape (n_intervals,)). Facility ids not present in the matrix are
    ignored. NaNs are treated as 0 in the sum.
    """
    try:
        facility_ids, matrix = load_year_matrix(year)
    except FacilityScadaMatrix.DoesNotExist:
        return np.array([], dtype='float32')
    idx = facility_row_index(facility_ids)
    rows = [idx[fid] for fid in facility_ids_wanted if fid in idx]
    if not rows:
        return np.zeros(matrix.shape[1], dtype=matrix.dtype)
    return np.nansum(matrix[rows, :], axis=0)


def year_totals(year: int, facility_ids_wanted=None, positive_only: bool = False):
    """
    Return the 1-D per-interval total (shape (n_intervals,)) summed across
    all facilities in `year`'s matrix, or just `facility_ids_wanted` if
    given. If positive_only, negative/NaN cells count as 0 before summing
    (mirrors `Sum(Case(When(quantity__gt=0, then=F('quantity'))))`, used
    throughout for "total generation" excluding storage/pumping charge).
    """
    facility_ids, matrix = load_year_matrix(year)
    if facility_ids_wanted is not None:
        idx = facility_row_index(facility_ids)
        rows = [idx[fid] for fid in facility_ids_wanted if fid in idx]
        matrix = matrix[rows, :] if rows else np.empty((0, matrix.shape[1]), dtype=matrix.dtype)
    if matrix.shape[0] == 0:
        return np.zeros(matrix.shape[1] if matrix.ndim == 2 else 0, dtype='float32')
    if positive_only:
        with np.errstate(invalid='ignore'):
            matrix = np.where(matrix > 0, matrix, 0.0)
        return np.sum(matrix, axis=0)
    with np.errstate(invalid='ignore'):
        return np.nansum(matrix, axis=0)


def facility_matrix_for_datetime_range(start_dt, end_dt_exclusive, facility_ids_wanted=None):
    """
    Return (facility_ids, matrix_slice) for [start_dt, end_dt_exclusive),
    matrix_slice shape (len(facility_ids), n_intervals_in_range). The range
    must lie within a single UTC calendar year (raises ValueError
    otherwise) -- for per-facility/per-technology breakdowns (e.g. a
    calendar month), which never cross a year boundary; use
    total_for_datetime_range/cell_counts_for_datetime_range instead for
    across-facility totals that may span years.
    """
    start_utc = _floor_to_half_hour(start_dt.astimezone(dt_timezone.utc))
    end_utc = _floor_to_half_hour(end_dt_exclusive.astimezone(dt_timezone.utc))
    last_year = (end_utc - timedelta(minutes=30)).year
    if start_utc.year != last_year:
        raise ValueError(
            f"facility_matrix_for_datetime_range range spans years {start_utc.year}-{last_year}; "
            "not supported (facility identity isn't stable across years)"
        )

    year = start_utc.year
    facility_ids, matrix = load_year_matrix(year)
    if facility_ids_wanted is not None:
        idx = facility_row_index(facility_ids)
        rows = [idx[fid] for fid in facility_ids_wanted if fid in idx]
        facility_ids = [facility_ids[r] for r in rows]
        matrix = matrix[rows, :] if rows else np.empty((0, matrix.shape[1]), dtype=matrix.dtype)

    year_start = datetime(year, 1, 1, tzinfo=dt_timezone.utc)
    start_idx = round((start_utc - year_start).total_seconds() / 1800)
    end_idx = round((end_utc - year_start).total_seconds() / 1800)
    return facility_ids, matrix[:, max(start_idx, 0):min(end_idx, matrix.shape[1])]


def _stitch_per_interval(start_dt, end_dt_exclusive, year_array_func, fill_value=np.nan):
    """
    Stitch together a 1-D per-interval array for [start_dt, end_dt_exclusive)
    from one or more years' worth of a caller-supplied per-year 1-D array
    (`year_array_func(year) -> np.ndarray` shape (n_intervals_in_year,)).
    start_dt/end_dt_exclusive are converted to true UTC via .astimezone()
    -- dispatch_interval is confirmed genuine UTC, so (unlike
    dpv_matrix.values_for_datetime_range) this performs a real conversion
    rather than reading wall-clock digits as-is. A year with no matrix row
    contributes `fill_value`.
    """
    start_utc = _floor_to_half_hour(start_dt.astimezone(dt_timezone.utc))
    end_utc = _floor_to_half_hour(end_dt_exclusive.astimezone(dt_timezone.utc))
    n = round((end_utc - start_utc).total_seconds() / 1800)
    if n <= 0:
        return np.array([], dtype='float32')

    result = np.full(n, fill_value, dtype='float32')

    first_year, last_year = start_utc.year, (end_utc - timedelta(minutes=30)).year
    for year in range(first_year, last_year + 1):
        try:
            arr = year_array_func(year)
        except FacilityScadaMatrix.DoesNotExist:
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
        result[dst_start:dst_end] = arr[src_start:src_end]

    return result


def facility_trace_for_datetime_range(start_dt, end_dt_exclusive, facility_id):
    """
    1-D half-hourly trace for one facility across [start_dt,
    end_dt_exclusive), stitching across a year boundary if needed. NaN
    where the facility has no row in a spanned year, or the year itself
    has no matrix row at all.
    """
    def _year_trace(year):
        trace = facility_trace(year, facility_id)
        if trace is None:
            raise FacilityScadaMatrix.DoesNotExist
        return trace

    return _stitch_per_interval(start_dt, end_dt_exclusive, _year_trace)


def total_for_datetime_range(start_dt, end_dt_exclusive, facility_ids_wanted=None, positive_only: bool = False):
    """
    Return the 1-D per-interval total across facilities for the range
    [start_dt, end_dt_exclusive), stitching across a year boundary if
    needed.
    """
    return _stitch_per_interval(
        start_dt, end_dt_exclusive,
        lambda year: year_totals(year, facility_ids_wanted, positive_only),
    )


def cell_counts_for_datetime_range(start_dt, end_dt_exclusive, facility_ids_wanted=None):
    """
    Per-interval count of non-NaN facility cells (i.e. how many facilities
    have data) for [start_dt, end_dt_exclusive). Years with no matrix row
    contribute 0, not NaN -- "no data" is a definite zero here.
    """
    def _counts(year):
        facility_ids, matrix = load_year_matrix(year)
        if facility_ids_wanted is not None:
            idx = facility_row_index(facility_ids)
            rows = [idx[fid] for fid in facility_ids_wanted if fid in idx]
            matrix = matrix[rows, :] if rows else np.empty((0, matrix.shape[1]), dtype=matrix.dtype)
        if matrix.shape[0] == 0:
            return np.zeros(matrix.shape[1], dtype='float32')
        return np.count_nonzero(~np.isnan(matrix), axis=0).astype('float32')

    return np.nan_to_num(_stitch_per_interval(start_dt, end_dt_exclusive, _counts, fill_value=0.0), nan=0.0)


def facility_monthly_totals(year: int, month: int):
    """
    Return {facility_id: (total_mwh, record_count)} for every facility
    present in `year`'s matrix, for calendar month `month` (UTC calendar,
    matching dispatch_interval__year/__month lookups elsewhere).
    record_count is the number of non-NaN half-hourly intervals -- mirrors
    the old `Count('scada_records', filter=...)` semantics.
    """
    try:
        facility_ids, matrix = load_year_matrix(year)
    except FacilityScadaMatrix.DoesNotExist:
        return {}
    start = _index_for_date(date(year, month, 1), 1)
    end = start + monthrange(year, month)[1] * INTERVALS_PER_DAY
    sub = matrix[:, start:end]
    with np.errstate(invalid='ignore'):
        sums = np.nansum(sub, axis=1)
    counts = np.count_nonzero(~np.isnan(sub), axis=1)
    return {fid: (float(sums[i]), int(counts[i])) for i, fid in enumerate(facility_ids)}


def set_scada_values(records):
    """
    Upsert half-hourly records into the packed matrix.

    records: iterable of dicts with facility_id, dispatch_interval (any
    aware datetime -- converted to true UTC here) and quantity (float-like,
    half-hourly MWh). Records are grouped by (UTC year, facility_id); each
    facility's row in each affected year's matrix is patched in place
    (existing values elsewhere are left untouched), mirroring the raw-SQL
    "ON DUPLICATE KEY UPDATE" upsert this replaces.
    """
    by_year = defaultdict(lambda: defaultdict(list))
    for r in records:
        dt_utc = r['dispatch_interval'].astimezone(dt_timezone.utc)
        by_year[dt_utc.year][r['facility_id']].append((dt_utc, float(r['quantity'])))

    for year, facility_map in by_year.items():
        n = _intervals_in_year(year)
        try:
            row = FacilityScadaMatrix.objects.get(year=year)
            facility_ids = list(row.facility_ids)
            _, matrix = row.unpack()
            matrix = matrix.copy()
            if matrix.shape[1] != n:
                fixed = np.full((matrix.shape[0], n), np.nan, dtype='float32')
                w = min(n, matrix.shape[1])
                fixed[:, :w] = matrix[:, :w]
                matrix = fixed
        except FacilityScadaMatrix.DoesNotExist:
            facility_ids = []
            matrix = np.empty((0, n), dtype='float32')

        for facility_id, values in facility_map.items():
            if facility_id in facility_ids:
                i = facility_ids.index(facility_id)
            else:
                facility_ids.append(facility_id)
                new_row = np.full((1, n), np.nan, dtype='float32')
                matrix = np.vstack([matrix, new_row]) if matrix.shape[0] else new_row
                i = len(facility_ids) - 1

            for dt_utc, qty in values:
                idx = _index_for_datetime_utc(dt_utc)
                if 0 <= idx < n:
                    matrix[i, idx] = qty

        FacilityScadaMatrix.objects.update_or_create(
            year=year,
            defaults=dict(facility_ids=facility_ids, n_intervals=n, dtype='float32', data=matrix.tobytes()),
        )
        _cache.pop(year, None)
