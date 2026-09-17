"""
Time series alignment service for comparing SCADA and SupplyFactors data.

SCADA data is stored at half-hourly intervals (2 records per hour).
SupplyFactors data has hourly granularity (hour 1-8760 per year).

This service provides utilities to align these different time formats
for comparison and analysis.
"""

from typing import Optional
import numpy as np
from django.db.models import QuerySet

from siren_web.models import FacilityScadaMatrix, SupplyFactorMatrix
from siren_web.services import supply_matrix
from siren_web.services import facility_scada_matrix
from .generation_utils import get_hour_of_day, PEAK_HOUR_PRESETS


class TimeSeriesAligner:
    """Aligns SCADA (5-min datetime) with SupplyFactors (year+hour) data."""

    def convert_scada_to_hourly(self, year: int, facility_id: int,
                                 start_hour: Optional[int] = None,
                                 end_hour: Optional[int] = None) -> dict:
        """Convert one facility's SCADA half-hourly trace to hourly totals,
        read from the packed per-year FacilityScadaMatrix.

        SCADA has 2 records per hour (half-hourly intervals). This sums
        each pair to hourly MWh (numerically equal to average MW) to match
        SupplyFactors format. Hour numbering matches get_hour_of_year
        (1-based) -- the matrix is indexed by true UTC, the same basis
        get_hour_of_year uses for a UTC-aware `dispatch_interval` (matrix
        half-hour index i -> hour_of_year = i // 2 + 1).

        Args:
            year: Year to fetch
            facility_id: facilities.idfacilities to fetch
            start_hour: Optional start hour filter (1-based)
            end_hour: Optional end hour filter (1-based)

        Returns:
            Dict with 'hours' and 'quantity' lists
        """
        try:
            trace = facility_scada_matrix.facility_trace(year, facility_id)
        except FacilityScadaMatrix.DoesNotExist:
            trace = None

        if trace is None:
            return {'hours': [], 'quantity': [], 'record_count': 0, 'hour_count': 0}

        n_hours = trace.shape[0] // 2
        paired = trace[:n_hours * 2].reshape(n_hours, 2)
        with np.errstate(invalid='ignore'):
            has_data = ~np.all(np.isnan(paired), axis=1)
            hourly = np.nansum(paired, axis=1)

        hours = []
        quantities = []
        for h in range(n_hours):
            if not has_data[h]:
                continue
            hour_of_year = h + 1
            if start_hour is not None and hour_of_year < start_hour:
                continue
            if end_hour is not None and hour_of_year > end_hour:
                continue
            hours.append(hour_of_year)
            quantities.append(float(hourly[h]))

        return {
            'hours': hours,
            'quantity': quantities,
            'record_count': len(hours),
            'hour_count': len(hours)
        }

    def convert_scada_to_hourly_aggregated(self, year: int, facility_ids,
                                            start_hour: Optional[int] = None,
                                            end_hour: Optional[int] = None) -> dict:
        """Convert SCADA half-hourly data to hourly, summing across multiple
        facilities, read from the packed per-year FacilityScadaMatrix.

        For each facility, the two half-hourly MWh values per hour are
        summed to get hourly MWh, then summed across facilities. An hour
        only counts if at least one selected facility has at least one of
        its two half-hours present -- matches the original's "only hours
        with a real row" semantics.

        Args:
            year: Year being processed
            facility_ids: Iterable of facilities.idfacilities to sum
            start_hour: Optional start hour filter
            end_hour: Optional end hour filter

        Returns:
            Dict with 'hours' and 'quantity' lists (summed across facilities)
        """
        try:
            matrix_facility_ids, matrix = facility_scada_matrix.load_year_matrix(year)
        except FacilityScadaMatrix.DoesNotExist:
            return {'hours': [], 'quantity': [], 'hour_count': 0}

        idx = facility_scada_matrix.facility_row_index(matrix_facility_ids)
        rows = [idx[fid] for fid in facility_ids if fid in idx]
        if not rows:
            return {'hours': [], 'quantity': [], 'hour_count': 0}

        selected = matrix[rows, :]
        n_hours = selected.shape[1] // 2
        paired = selected[:, :n_hours * 2].reshape(len(rows), n_hours, 2)
        with np.errstate(invalid='ignore'):
            has_data = ~np.all(np.isnan(paired), axis=(0, 2))
            hourly = np.nansum(paired, axis=(0, 2))

        hours = []
        quantities = []
        for h in range(n_hours):
            if not has_data[h]:
                continue
            hour_of_year = h + 1
            if start_hour is not None and hour_of_year < start_hour:
                continue
            if end_hour is not None and hour_of_year > end_hour:
                continue
            hours.append(hour_of_year)
            quantities.append(float(hourly[h]))

        return {
            'hours': hours,
            'quantity': quantities,
            'hour_count': len(hours)
        }

    def get_supply_data_as_dict(self, year: int, facility_id: int,
                                 start_hour: Optional[int] = None,
                                 end_hour: Optional[int] = None) -> dict:
        """Get one facility's supply trace for a year in standard dict format,
        read from the packed per-year SupplyFactorMatrix.

        Args:
            year: Year to fetch
            facility_id: facilities.idfacilities to fetch
            start_hour: Optional start hour filter
            end_hour: Optional end hour filter

        Returns:
            Dict with 'hours' and 'quantum' lists (quantum converted from kW to MW)
        """
        try:
            trace = supply_matrix.facility_trace(year, facility_id)
        except SupplyFactorMatrix.DoesNotExist:
            trace = None

        if trace is None:
            return {'hours': [], 'quantum': [], 'hour_count': 0}

        hours = []
        quantum_values = []

        for hour, value in enumerate(trace):
            if start_hour is not None and hour < start_hour:
                continue
            if end_hour is not None and hour > end_hour:
                continue
            if np.isnan(value):
                # No supplyfactors row ever existed for this hour — matches
                # the original queryset simply not returning that row.
                continue

            hours.append(hour)
            # Convert quantum from kW to MW to match SCADA units
            quantum_values.append(float(value) / 1000)

        return {
            'hours': hours,
            'quantum': quantum_values,
            'hour_count': len(hours)
        }

    def get_supply_data_aggregated(self, year: int, facility_ids,
                                    start_hour: Optional[int] = None,
                                    end_hour: Optional[int] = None) -> dict:
        """Get supply data summed across multiple facilities for a year,
        read from the packed per-year SupplyFactorMatrix.

        Args:
            year: Year to fetch
            facility_ids: Iterable of facilities.idfacilities to sum
            start_hour: Optional start hour filter
            end_hour: Optional end hour filter

        Returns:
            Dict with 'hours' and 'quantum' lists (summed across facilities, converted from kW to MW)
        """
        try:
            matrix_facility_ids, matrix = supply_matrix.load_year_matrix(year)
        except SupplyFactorMatrix.DoesNotExist:
            return {'hours': [], 'quantum': [], 'hour_count': 0}

        idx = supply_matrix.facility_row_index(matrix_facility_ids)
        rows = [idx[fid] for fid in facility_ids if fid in idx]
        if not rows:
            return {'hours': [], 'quantum': [], 'hour_count': 0}

        selected = matrix[rows, :]
        # An hour only counts if at least one selected facility actually has
        # a value there — matches the original's "only hours with a real
        # row" semantics rather than padding entirely-missing hours with 0.
        has_data = ~np.all(np.isnan(selected), axis=0)
        sums = np.nansum(selected, axis=0)

        hours = []
        quantum_values = []
        for hour in range(matrix.shape[1]):
            if not has_data[hour]:
                continue
            if start_hour is not None and hour < start_hour:
                continue
            if end_hour is not None and hour > end_hour:
                continue

            hours.append(hour)
            # Convert quantum from kW to MW to match SCADA units
            quantum_values.append(float(sums[hour]) / 1000)

        return {
            'hours': hours,
            'quantum': quantum_values,
            'hour_count': len(hours)
        }

    def align_scada_and_supply(self, scada_data: dict, supply_data: dict) -> Optional[dict]:
        """Align SCADA and SupplyFactors data by hour.

        Only returns hours present in BOTH datasets.

        Args:
            scada_data: Dict with 'hours' and 'quantity' from SCADA
            supply_data: Dict with 'hours' and 'quantum' from SupplyFactors

        Returns:
            Dict with aligned data, or None if no overlap
        """
        scada_hours = set(scada_data.get('hours', []))
        supply_hours = set(supply_data.get('hours', []))
        common_hours = sorted(scada_hours & supply_hours)

        if not common_hours:
            return None

        # Create lookup dicts
        scada_dict = dict(zip(scada_data['hours'], scada_data['quantity']))
        supply_dict = dict(zip(supply_data['hours'], supply_data['quantum']))

        # Calculate overlap statistics
        total_hours = len(scada_hours | supply_hours)
        overlap_pct = (len(common_hours) / total_hours * 100) if total_hours > 0 else 0

        scada_only = len(scada_hours - supply_hours)
        supply_only = len(supply_hours - scada_hours)

        return {
            'hours': common_hours,
            'scada_values': [scada_dict[h] for h in common_hours],
            'supply_values': [supply_dict[h] for h in common_hours],
            'overlap_percentage': round(overlap_pct, 1),
            'common_hours': len(common_hours),
            'scada_only_hours': scada_only,
            'supply_only_hours': supply_only,
            'total_unique_hours': total_hours
        }

    def filter_aligned_to_peak_hours(self, aligned_data: dict,
                                      peak_preset: str = 'peak') -> Optional[dict]:
        """Filter aligned data to only include peak hours.

        This helps reduce the impact of curtailment on the comparison,
        as curtailment is less likely during peak demand hours.

        Args:
            aligned_data: Dict from align_scada_and_supply()
            peak_preset: Key from PEAK_HOUR_PRESETS ('all', 'peak', 'shoulder',
                        'off_peak', 'daytime', 'solar_peak')

        Returns:
            Filtered aligned data dict, or None if no data after filtering
        """
        if aligned_data is None:
            return None

        preset = PEAK_HOUR_PRESETS.get(peak_preset, PEAK_HOUR_PRESETS['peak'])
        peak_start = preset['start']
        peak_end = preset['end']

        # Handle 'all' case - return original data
        if peak_preset == 'all':
            return aligned_data

        # Handle wrap-around for off-peak (e.g., 21:00 to 07:00)
        if peak_start > peak_end:
            # Off-peak spans midnight
            def is_in_range(hour_of_day):
                return hour_of_day >= peak_start or hour_of_day < peak_end
        else:
            def is_in_range(hour_of_day):
                return peak_start <= hour_of_day < peak_end

        filtered_hours = []
        filtered_scada = []
        filtered_supply = []

        for i, hour in enumerate(aligned_data['hours']):
            hour_of_day = get_hour_of_day(hour)
            if is_in_range(hour_of_day):
                filtered_hours.append(hour)
                filtered_scada.append(aligned_data['scada_values'][i])
                filtered_supply.append(aligned_data['supply_values'][i])

        if not filtered_hours:
            return None

        # Calculate new overlap statistics for filtered data
        total_filtered = len(filtered_hours)
        original_total = len(aligned_data['hours'])
        filter_pct = (total_filtered / original_total * 100) if original_total > 0 else 0

        return {
            'hours': filtered_hours,
            'scada_values': filtered_scada,
            'supply_values': filtered_supply,
            'overlap_percentage': aligned_data['overlap_percentage'],
            'common_hours': total_filtered,
            'scada_only_hours': aligned_data['scada_only_hours'],
            'supply_only_hours': aligned_data['supply_only_hours'],
            'total_unique_hours': aligned_data['total_unique_hours'],
            'peak_filter_applied': peak_preset,
            'peak_filter_label': preset['label'],
            'hours_after_filter': total_filtered,
            'filter_retention_pct': round(filter_pct, 1)
        }

    def get_comparable_years(self) -> list[int]:
        """Get years that have both SCADA and matrix (SupplyFactorMatrix) data.

        Returns:
            Sorted list of years with data in both
        """
        scada_years = set(FacilityScadaMatrix.objects.values_list('year', flat=True))
        supply_years = set(SupplyFactorMatrix.objects.values_list('year', flat=True))
        return sorted(scada_years & supply_years)

    def get_comparable_facilities(self, facilities_model,
                                   year: Optional[int] = None) -> QuerySet:
        """Get facilities that have both SCADA and matrix data.

        The matrix only holds renewable, non-dispatchable facility traces in
        practice (it mirrors supplyfactors, which had the same constraint),
        so this also filters to those characteristics.

        Args:
            facilities_model: facilities model class
            year: Optional year to check for data availability

        Returns:
            QuerySet of facilities with both data sources
        """
        # Start with renewable, non-dispatchable (matrix constraint)
        base_qs = facilities_model.objects.filter(
            idtechnologies__renewable=1,
            idtechnologies__dispatchable=0
        ).select_related('idtechnologies')

        # Get facility IDs that appear in the SCADA matrix (a given year's
        # row, or any year's if none specified) -- FacilityScadaMatrix has
        # no FK/reverse relation to facilities, unlike the old
        # `scada_records__isnull=False` reverse-FK filter this replaces, so
        # membership is checked against facility_ids directly, the same way
        # the SupplyFactorMatrix side already works below.
        scada_rows = FacilityScadaMatrix.objects.only('facility_ids')
        if year:
            scada_rows = scada_rows.filter(year=year)

        facilities_with_scada = set()
        for row in scada_rows:
            facilities_with_scada.update(row.facility_ids)

        # Get facility IDs that appear in the matrix (a given year's row, or
        # any year's if none specified)
        matrix_rows = SupplyFactorMatrix.objects.only('facility_ids')
        if year:
            matrix_rows = matrix_rows.filter(year=year)

        facilities_with_supply = set()
        for row in matrix_rows:
            facilities_with_supply.update(row.facility_ids)

        # Intersection
        common_facilities = facilities_with_scada & facilities_with_supply

        return base_qs.filter(
            idfacilities__in=common_facilities
        ).distinct().order_by('facility_name')

    def get_comparable_technologies(self, technologies_model, facilities_model,
                                     year: Optional[int] = None) -> QuerySet:
        """Get technologies that have facilities with both data sources.

        Args:
            technologies_model: Technologies model class
            facilities_model: facilities model class
            year: Optional year to check

        Returns:
            QuerySet of technologies with comparable facilities
        """
        comparable_facilities = self.get_comparable_facilities(
            facilities_model, year
        )

        tech_ids = comparable_facilities.values_list(
            'idtechnologies', flat=True
        ).distinct()

        return technologies_model.objects.filter(
            idtechnologies__in=tech_ids,
            renewable=1,
            dispatchable=0
        ).order_by('technology_name')
