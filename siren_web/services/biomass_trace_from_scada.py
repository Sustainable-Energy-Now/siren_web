"""
Builds real hourly generation traces for Biomass facilities from their own
FacilityScadaMatrix history (2024/2025) and writes them into
SupplyFactorMatrix, so the dispatch engine can use them as a fixed
non-dispatchable trace instead of economically optimizing biomass output
(see biomass_dispatch_split.py for the Technologies.dispatchable flip and
the "no real trace" facility split).

Each calendar year is evaluated and stored independently, matching how
Wind/Solar traces already work: a facility gets a real trace for whichever
of TRACE_YEARS it has enough SCADA coverage for, and simply has no row for a
year it doesn't clear the threshold for (see biomass_dispatch_split.build_plan
for how that's combined with the "at least one qualifying year" rule at the
facility level).

FacilityScadaMatrix is half-hourly, genuinely UTC-indexed, values in MWh.
SupplyFactorMatrix is hourly, fixed at 8760 hours/year system-wide (confirmed:
powermapui.views.power_views.store_simulation_results hardcodes
end_hour=8759), values in kW, and built on a local Perth-clock calendar (no
UTC conversion in the SAM write path) -- so traces here are built on
Perth-local hour boundaries, not raw UTC calendar days. For a leap year
(2024), the local calendar has 366 days = 8784 hours; 29 Feb's 24 hours are
deliberately dropped so every trace this module writes stays exactly 8760
hours, aligned with every other technology's row for that year. This is a
small, real, and deliberate loss of data -- surfaced via dropped_leap_day on
the result, not silent.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np

from siren_web.models import Technologies, facilities
from siren_web.services import supply_matrix
from siren_web.services.facility_scada_matrix import facility_trace_for_datetime_range

MIN_COVERAGE_DEFAULT = 0.9
TRACE_YEARS = (2024, 2025)
HOURS_PER_YEAR = 8760
PERTH = ZoneInfo("Australia/Perth")  # fixed UTC+8, no DST


@dataclass
class BiomassTraceResult:
    facility_id: int
    facility_name: str
    coverage_by_year: dict = field(default_factory=dict)     # {year: fraction}
    qualifying_years: list = field(default_factory=list)     # years >= min_coverage
    dropped_leap_day: list = field(default_factory=list)     # years where 29 Feb was dropped
    hours_written: dict = field(default_factory=dict)        # {year: non-NaN hour count}

    @property
    def moves_to_twin(self) -> bool:
        return len(self.qualifying_years) == 0


def get_biomass_technology() -> Technologies:
    """Look up the Biomass technology by name (not the conventionally
    hardcoded idtechnologies=6 used by the facility-import commands)."""
    try:
        technology = Technologies.objects.get(technology_name='Biomass')
    except Technologies.DoesNotExist:
        raise Technologies.DoesNotExist("No Technologies row named 'Biomass' found.")
    if technology.fuel_type != 'BIOMASS' or technology.category != 'Generator':
        raise ValueError(
            f"Technologies 'Biomass' (id={technology.idtechnologies}) has "
            f"fuel_type={technology.fuel_type!r}, category={technology.category!r} "
            "-- expected fuel_type='BIOMASS', category='Generator'."
        )
    return technology


def list_biomass_facilities(technology: Technologies | None = None):
    return facilities.objects.filter(idtechnologies=technology or get_biomass_technology())


def _local_year_bounds(year: int):
    """Perth-local midnight 1 Jan `year` -> Perth-local midnight 1 Jan `year+1`."""
    return datetime(year, 1, 1, tzinfo=PERTH), datetime(year + 1, 1, 1, tzinfo=PERTH)


def facility_half_hourly_for_year(facility_id: int, year: int) -> np.ndarray:
    """Half-hourly MWh trace for one facility across the Perth-local calendar
    year `year` (not the UTC calendar year), stitched across the underlying
    UTC year boundary as needed. NaN where source data is missing."""
    start, end = _local_year_bounds(year)
    return facility_trace_for_datetime_range(start, end, facility_id)


def coverage_for_year(facility_id: int, year: int) -> float:
    trace = facility_half_hourly_for_year(facility_id, year)
    if trace.size == 0:
        return 0.0
    with np.errstate(invalid='ignore'):
        return float(np.mean(~np.isnan(trace)))


def analyze(min_coverage: float = MIN_COVERAGE_DEFAULT, years=TRACE_YEARS) -> list:
    """For every Biomass facility, compute per-year coverage and which years
    individually clear min_coverage."""
    technology = get_biomass_technology()
    results = []
    for facility in list_biomass_facilities(technology).order_by('idfacilities'):
        result = BiomassTraceResult(facility_id=facility.idfacilities, facility_name=facility.facility_name)
        for year in years:
            coverage = coverage_for_year(facility.idfacilities, year)
            result.coverage_by_year[year] = coverage
            if coverage >= min_coverage:
                result.qualifying_years.append(year)
        results.append(result)
    return results


def build_hourly_kw_trace(facility_id: int, year: int):
    """
    Returns (trace, dropped_leap_day): trace is an HOURS_PER_YEAR-length
    float32 array of kW (NaN where still missing after pairing), and
    dropped_leap_day is True if 29 Feb's data was discarded to keep the
    trace at exactly 8760 hours.
    """
    half_hourly = facility_half_hourly_for_year(facility_id, year)
    if half_hourly.size % 48 != 0:
        raise ValueError(
            f"facility {facility_id} year {year}: half-hourly trace length "
            f"{half_hourly.size} is not a multiple of 48."
        )
    n_days = half_hourly.size // 48

    half_hourly = half_hourly.reshape(n_days, 48)
    first_half = half_hourly[:, 0::2]
    second_half = half_hourly[:, 1::2]
    with np.errstate(invalid='ignore'):
        hourly = first_half + second_half  # MWh over the hour == that hour's average MW
        hourly[np.isnan(first_half) | np.isnan(second_half)] = np.nan
    hourly = hourly.reshape(-1)  # (n_days * 24,)

    dropped_leap_day = False
    if n_days == 366:
        hourly = np.delete(hourly, np.s_[59 * 24:60 * 24])  # 29 Feb (0-based day 59)
        dropped_leap_day = True
    elif n_days != 365:
        raise ValueError(f"facility {facility_id} year {year}: unexpected day count {n_days}.")

    with np.errstate(invalid='ignore'):
        hourly = np.where(hourly < 0, 0.0, hourly)
    kw = (hourly * supply_matrix.TRACE_KW_PER_MW).astype('float32')
    return kw, dropped_leap_day


def build_traces(results: list, dry_run: bool = False) -> dict:
    """For every facility with at least one qualifying year, build and write
    (unless dry_run) a trace for each of its qualifying years. Mutates each
    result's hours_written/dropped_leap_day in place."""
    facilities_with_trace = 0
    for result in results:
        if result.moves_to_twin:
            continue
        facilities_with_trace += 1
        for year in result.qualifying_years:
            trace, dropped = build_hourly_kw_trace(result.facility_id, year)
            if dropped:
                result.dropped_leap_day.append(year)
            result.hours_written[year] = int(np.count_nonzero(~np.isnan(trace)))
            if not dry_run:
                supply_matrix.clear_facility_trace(year, result.facility_id)
                supply_matrix.set_facility_trace(year, result.facility_id, trace, start_hour=0)

    return {
        'facilities_with_trace': facilities_with_trace,
        'facilities_to_twin': len(results) - facilities_with_trace,
        'results': results,
    }
