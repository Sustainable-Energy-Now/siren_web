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
