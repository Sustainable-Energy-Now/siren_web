"""
Loader for DemandMatrix — the per-year (demand x interval) trace store for
the Demand model, mirroring supply_matrix.py's SupplyFactorMatrix loader.

One DemandMatrix row holds every Demand's half-hourly trace for a year as a
packed float array. This is the Demand-side counterpart of SupplyFactorMatrix
— a Demand has exactly one trace (never summed with others), but the same
packed-matrix-per-year storage shape is reused for consistency with the rest
of this project's time-series tables.
"""
import numpy as np

from siren_web.models import DemandMatrix

# Process-local cache keyed by year: (demand_ids, matrix, updated_at).
# Invalidated automatically by comparing updated_at.
_cache = {}


def load_year_matrix(year: int):
    """
    Return (demand_ids, matrix) for a year, where matrix has shape
    (len(demand_ids), n_hours) and matrix[i, :] is demand_ids[i]'s trace.
    Missing values are NaN.
    """
    row = DemandMatrix.objects.get(year=year)

    cached = _cache.get(year)
    if cached is not None and cached[2] == row.updated_at:
        return cached[0], cached[1]

    demand_ids, matrix = row.unpack()
    _cache[year] = (demand_ids, matrix, row.updated_at)
    return demand_ids, matrix


def demand_row_index(demand_ids):
    """Map demand id -> row index into the matrix returned by load_year_matrix."""
    return {did: i for i, did in enumerate(demand_ids)}


def demand_trace(year: int, demand_id: int):
    """Return the 1-D trace for a single Demand, or None if absent."""
    demand_ids, matrix = load_year_matrix(year)
    idx = demand_row_index(demand_ids)
    i = idx.get(demand_id)
    if i is None:
        return None
    return matrix[i, :]


def demand_has_trace(year: int, demand_id: int) -> bool:
    """Whether demand_id has a row in year's matrix at all (no NaN check)."""
    try:
        demand_ids, _ = load_year_matrix(year)
    except DemandMatrix.DoesNotExist:
        return False
    return demand_id in demand_ids


def demands_trace_sum(year: int, demand_ids_wanted):
    """
    Return the elementwise sum across the given demand ids' traces
    (shape (n_hours,)). Demand ids not present in the matrix are ignored.
    NaNs are treated as 0 in the sum.
    """
    demand_ids, matrix = load_year_matrix(year)
    idx = demand_row_index(demand_ids)
    rows = [idx[did] for did in demand_ids_wanted if did in idx]
    if not rows:
        return np.zeros(matrix.shape[1], dtype=matrix.dtype)
    return np.nansum(matrix[rows, :], axis=0)


def set_demand_trace(year: int, demand_id: int, values, start_hour: int = 0):
    """
    Write `values` (1-D array-like) into demand_id's row for `year` starting
    at `start_hour`, replacing just that sub-range. Creates the year's
    matrix and/or the demand's row (NaN-filled outside the given range) if
    either doesn't exist yet, and grows the matrix's hour dimension if
    `values` reaches past its current width.

    Call this wherever a Demand's trace is (re)generated (ESOO/EV scenario
    builders) so the matrix stays in sync.
    """
    values = np.asarray(values, dtype='float32')
    end_hour = start_hour + values.shape[0]

    try:
        row = DemandMatrix.objects.get(year=year)
        demand_ids, matrix = row.unpack()
        demand_ids = list(demand_ids)
        matrix = matrix.copy()  # unpack() is a read-only view over row.data
    except DemandMatrix.DoesNotExist:
        demand_ids = []
        matrix = np.empty((0, end_hour), dtype='float32')

    if end_hour > matrix.shape[1]:
        pad = np.full((matrix.shape[0], end_hour - matrix.shape[1]), np.nan, dtype='float32')
        matrix = np.hstack([matrix, pad]) if matrix.shape[0] else np.empty((0, end_hour), dtype='float32')

    if demand_id in demand_ids:
        i = demand_ids.index(demand_id)
    else:
        demand_ids.append(demand_id)
        matrix = np.vstack([matrix, np.full((1, matrix.shape[1]), np.nan, dtype='float32')])
        i = len(demand_ids) - 1

    matrix[i, start_hour:end_hour] = values

    DemandMatrix.objects.update_or_create(
        year=year,
        defaults=dict(
            demand_ids=demand_ids,
            n_hours=matrix.shape[1],
            dtype='float32',
            data=matrix.tobytes(),
        ),
    )
    _cache.pop(year, None)


def clear_demand_trace(year: int, demand_id: int, start_hour: int = None, end_hour: int = None):
    """
    NaN-out a demand's hours for `year` — the whole row by default, or the
    inclusive [start_hour, end_hour] range if given. No-op if the year or
    demand isn't present yet. Mirrors clear_facility_trace's idempotent-
    regeneration pattern.
    """
    try:
        row = DemandMatrix.objects.get(year=year)
    except DemandMatrix.DoesNotExist:
        return

    demand_ids, matrix = row.unpack()
    if demand_id not in demand_ids:
        return

    matrix = matrix.copy()
    i = demand_ids.index(demand_id)
    s = start_hour if start_hour is not None else 0
    e = (end_hour + 1) if end_hour is not None else matrix.shape[1]
    matrix[i, s:e] = np.nan

    row.data = matrix.tobytes()
    row.save(update_fields=['data', 'updated_at'])
    _cache.pop(year, None)
