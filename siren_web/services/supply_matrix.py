"""
Loader for SupplyFactorMatrix — the per-year (facility x hour) replacement
for the row-per-hour `supplyfactors` table.

One SupplyFactorMatrix row holds every facility's hourly generation trace
for a year as a packed float array. Loading it is one query + one reshape,
and scenario recombination becomes a single vectorised operation over the
in-memory matrix instead of per-facility ORM filtering.
"""
import numpy as np

from siren_web.models import SupplyFactorMatrix

# Process-local cache keyed by year: (facility_ids, matrix, updated_at).
# Invalidated automatically by comparing updated_at, so a rebuild via
# build_supply_factor_matrix is picked up without restarting the process.
_cache = {}


def load_year_matrix(year: int):
    """
    Return (facility_ids, matrix) for a year, where matrix has shape
    (len(facility_ids), n_hours) and matrix[i, :] is facility_ids[i]'s
    hourly trace. Missing values are NaN.
    """
    row = SupplyFactorMatrix.objects.get(year=year)

    cached = _cache.get(year)
    if cached is not None and cached[2] == row.updated_at:
        return cached[0], cached[1]

    facility_ids, matrix = row.unpack()
    _cache[year] = (facility_ids, matrix, row.updated_at)
    return facility_ids, matrix


def facility_row_index(facility_ids):
    """Map facility id -> row index into the matrix returned by load_year_matrix."""
    return {fid: i for i, fid in enumerate(facility_ids)}


def facility_trace(year: int, facility_id: int):
    """Return the 1-D hourly trace for a single facility, or None if absent."""
    facility_ids, matrix = load_year_matrix(year)
    idx = facility_row_index(facility_ids)
    i = idx.get(facility_id)
    if i is None:
        return None
    return matrix[i, :]


def facilities_trace_sum(year: int, facility_ids_wanted):
    """
    Return the elementwise sum across the given facility ids' traces
    (shape (n_hours,)), e.g. for a technology-group view. Facility ids not
    present in the matrix are ignored. NaNs are treated as 0 in the sum.
    """
    facility_ids, matrix = load_year_matrix(year)
    idx = facility_row_index(facility_ids)
    rows = [idx[fid] for fid in facility_ids_wanted if fid in idx]
    if not rows:
        return np.zeros(matrix.shape[1], dtype=matrix.dtype)
    return np.nansum(matrix[rows, :], axis=0)


def set_facility_trace(year: int, facility_id: int, values, start_hour: int = 0):
    """
    Write `values` (1-D array-like) into facility_id's row for `year`
    starting at `start_hour`, replacing just that sub-range. Creates the
    year's matrix and/or the facility's row (NaN-filled outside the given
    range) if either doesn't exist yet, and grows the matrix's hour
    dimension if `values` reaches past its current width.

    This is the write-side counterpart to load_year_matrix/facility_trace —
    call it wherever a facility's trace is (re)generated (SAM baseline,
    EV/ESOO load-trace synthesis) so the matrix stays in sync without a
    separate build_supply_factor_matrix backfill run.
    """
    values = np.asarray(values, dtype='float32')
    end_hour = start_hour + values.shape[0]

    try:
        row = SupplyFactorMatrix.objects.get(year=year)
        facility_ids, matrix = row.unpack()
        facility_ids = list(facility_ids)
        matrix = matrix.copy()  # unpack() is a read-only view over row.data
    except SupplyFactorMatrix.DoesNotExist:
        facility_ids = []
        matrix = np.empty((0, end_hour), dtype='float32')

    if end_hour > matrix.shape[1]:
        pad = np.full((matrix.shape[0], end_hour - matrix.shape[1]), np.nan, dtype='float32')
        matrix = np.hstack([matrix, pad]) if matrix.shape[0] else np.empty((0, end_hour), dtype='float32')

    if facility_id in facility_ids:
        i = facility_ids.index(facility_id)
    else:
        facility_ids.append(facility_id)
        matrix = np.vstack([matrix, np.full((1, matrix.shape[1]), np.nan, dtype='float32')])
        i = len(facility_ids) - 1

    matrix[i, start_hour:end_hour] = values

    SupplyFactorMatrix.objects.update_or_create(
        year=year,
        defaults=dict(
            facility_ids=facility_ids,
            n_hours=matrix.shape[1],
            dtype='float32',
            data=matrix.tobytes(),
        ),
    )
    _cache.pop(year, None)


def clear_facility_trace(year: int, facility_id: int, start_hour: int = None, end_hour: int = None):
    """
    NaN-out a facility's hours for `year` — the whole row by default, or
    the inclusive [start_hour, end_hour] range if given. No-op if the year
    or facility isn't present yet. Mirrors the "delete existing rows before
    inserting the new trace" idempotent-regeneration pattern the legacy
    supplyfactors writers used; set_facility_trace's own overwrite already
    covers the common case, so this only matters when a regenerated trace
    is shorter than what it's replacing.
    """
    try:
        row = SupplyFactorMatrix.objects.get(year=year)
    except SupplyFactorMatrix.DoesNotExist:
        return

    facility_ids, matrix = row.unpack()
    if facility_id not in facility_ids:
        return

    matrix = matrix.copy()
    i = facility_ids.index(facility_id)
    s = start_hour if start_hour is not None else 0
    e = (end_hour + 1) if end_hour is not None else matrix.shape[1]
    matrix[i, s:e] = np.nan

    row.data = matrix.tobytes()
    row.save(update_fields=['data', 'updated_at'])
    _cache.pop(year, None)
