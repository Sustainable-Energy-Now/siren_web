"""
Time series alignment service for comparing SCADA and SupplyFactors data.

SCADA data is stored at half-hourly intervals (2 records per hour).
SupplyFactors data has hourly granularity (hour 1-8760 per year).

This service provides utilities to align these different time formats
for comparison and analysis.
"""

from datetime import datetime
from typing import Optional
from django.db.models import QuerySet

from .generation_utils import get_hour_of_year, get_hour_of_day, PEAK_HOUR_PRESETS


class TimeSeriesAligner:
    """Aligns SCADA (5-min datetime) with SupplyFactors (year+hour) data."""

    def convert_scada_to_hourly(self, scada_queryset: QuerySet, year: int,
                                 start_hour: Optional[int] = None,
                                 end_hour: Optional[int] = None) -> dict:
        """Convert SCADA half-hourly data to hourly totals.

        SCADA has 2 records per hour (half-hourly intervals).
        This method sums quantity values for each hour of year
        to match SupplyFactors format. The sum of two half-hourly MWh
        values gives hourly MWh (numerically equal to average MW).

        Args:
            scada_queryset: FacilityScada queryset filtered by facility and year
            year: Year being processed (for context)
            start_hour: Optional start hour filter (1-based)
            end_hour: Optional end hour filter (1-based)

        Returns:
            Dict with 'hours' and 'quantity' lists
        """
        hour_totals = {}

        for record in scada_queryset:
            hour = get_hour_of_year(record.dispatch_interval)

            # Apply hour range filter if specified
            if start_hour is not None and hour < start_hour:
                continue
            if end_hour is not None and hour > end_hour:
                continue

            if hour not in hour_totals:
                hour_totals[hour] = 0

            quantity = float(record.quantity) if record.quantity else 0
            hour_totals[hour] += quantity

        # Sum of half-hourly MWh = hourly MWh = average MW for the hour
        hours = sorted(hour_totals.keys())
        quantities = [hour_totals[h] for h in hours]

        return {
            'hours': hours,
            'quantity': quantities,
            'record_count': sum(1 for _ in hours),
            'hour_count': len(hours)
        }

    def convert_scada_to_hourly_aggregated(self, scada_queryset: QuerySet, year: int,
                                            start_hour: Optional[int] = None,
                                            end_hour: Optional[int] = None) -> dict:
        """Convert SCADA half-hourly data to hourly, summing across multiple facilities.

        Similar to convert_scada_to_hourly but sums values across facilities.
        For each facility, the two half-hourly MWh values per hour are summed to
        get hourly MWh, then summed across facilities.

        Args:
            scada_queryset: FacilityScada queryset (can span multiple facilities)
            year: Year being processed
            start_hour: Optional start hour filter
            end_hour: Optional end hour filter

        Returns:
            Dict with 'hours' and 'quantity' lists (summed across facilities)
        """
        # Group by (facility, hour) and sum the half-hourly intervals
        facility_hour_data = {}

        for record in scada_queryset:
            hour = get_hour_of_year(record.dispatch_interval)

            if start_hour is not None and hour < start_hour:
                continue
            if end_hour is not None and hour > end_hour:
                continue

            facility_id = record.facility_id
            key = (facility_id, hour)

            if key not in facility_hour_data:
                facility_hour_data[key] = {'total': 0}

            quantity = float(record.quantity) if record.quantity else 0
            facility_hour_data[key]['total'] += quantity

        # Sum each facility's hourly total across facilities by hour
        hour_totals = {}
        for (facility_id, hour), data in facility_hour_data.items():
            hourly_quantity = data['total']  # Sum of half-hourly MWh = hourly MWh
            if hour not in hour_totals:
                hour_totals[hour] = 0
            hour_totals[hour] += hourly_quantity

        hours = sorted(hour_totals.keys())
        quantities = [hour_totals[h] for h in hours]

        return {
            'hours': hours,
            'quantity': quantities,
            'hour_count': len(hours)
        }

    def get_supply_data_as_dict(self, supply_queryset: QuerySet,
                                 start_hour: Optional[int] = None,
                                 end_hour: Optional[int] = None) -> dict:
        """Convert SupplyFactors queryset to standard dict format.

        Args:
            supply_queryset: supplyfactors queryset
            start_hour: Optional start hour filter
            end_hour: Optional end hour filter

        Returns:
            Dict with 'hours' and 'quantum' lists (quantum converted from kW to MW)
        """
        hours = []
        quantum_values = []

        for record in supply_queryset.order_by('hour'):
            hour = record.hour

            if start_hour is not None and hour < start_hour:
                continue
            if end_hour is not None and hour > end_hour:
                continue

            hours.append(hour)
            # Convert quantum from kW to MW to match SCADA units
            quantum_kw = record.quantum if record.quantum is not None else 0
            quantum_values.append(quantum_kw / 1000)

        return {
            'hours': hours,
            'quantum': quantum_values,
            'hour_count': len(hours)
        }

    def get_supply_data_aggregated(self, supply_queryset: QuerySet,
                                    start_hour: Optional[int] = None,
                                    end_hour: Optional[int] = None) -> dict:
        """Get SupplyFactors data summed across multiple facilities.

        Args:
            supply_queryset: supplyfactors queryset (can span multiple facilities)
            start_hour: Optional start hour filter
            end_hour: Optional end hour filter

        Returns:
            Dict with 'hours' and 'quantum' lists (summed across facilities, converted from kW to MW)
        """
        hour_totals = {}

        for record in supply_queryset:
            hour = record.hour

            if start_hour is not None and hour < start_hour:
                continue
            if end_hour is not None and hour > end_hour:
                continue

            if hour not in hour_totals:
                hour_totals[hour] = 0
            hour_totals[hour] += record.quantum if record.quantum is not None else 0

        hours = sorted(hour_totals.keys())
        # Convert quantum from kW to MW to match SCADA units
        quantum_values = [hour_totals[h] / 1000 for h in hours]

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

    def get_comparable_years(self, scada_model, supply_model) -> list[int]:
        """Get years that have both SCADA and SupplyFactors data.

        Args:
            scada_model: FacilityScada model class
            supply_model: supplyfactors model class

        Returns:
            Sorted list of years with data in both models
        """
        scada_years = set(
            scada_model.objects.dates('dispatch_interval', 'year', order='ASC')
            .values_list('dispatch_interval__year', flat=True)
        )
        supply_years = set(
            supply_model.objects.values_list('year', flat=True).distinct()
        )
        return sorted(scada_years & supply_years)

    def get_comparable_facilities(self, facilities_model, scada_model, supply_model,
                                   year: Optional[int] = None) -> QuerySet:
        """Get facilities that have both SCADA and SupplyFactors data.

        SupplyFactors only has data for renewable, non-dispatchable facilities,
        so this also filters to those characteristics.

        Args:
            facilities_model: facilities model class
            scada_model: FacilityScada model class
            supply_model: supplyfactors model class
            year: Optional year to check for data availability

        Returns:
            QuerySet of facilities with both data sources
        """
        # Start with renewable, non-dispatchable (SupplyFactors constraint)
        base_qs = facilities_model.objects.filter(
            idtechnologies__renewable=1,
            idtechnologies__dispatchable=0
        ).select_related('idtechnologies')

        # Get facility IDs that have SCADA data
        scada_filter = {'scada_records__isnull': False}
        if year:
            scada_filter['scada_records__dispatch_interval__year'] = year

        facilities_with_scada = set(
            base_qs.filter(**scada_filter).values_list('idfacilities', flat=True).distinct()
        )

        # Get facility IDs that have SupplyFactors data
        supply_filter = {}
        if year:
            supply_filter['year'] = year

        facilities_with_supply = set(
            supply_model.objects.filter(**supply_filter)
            .values_list('idfacilities', flat=True).distinct()
        )

        # Intersection
        common_facilities = facilities_with_scada & facilities_with_supply

        return base_qs.filter(
            idfacilities__in=common_facilities
        ).distinct().order_by('facility_name')

    def get_comparable_technologies(self, technologies_model, facilities_model,
                                     scada_model, supply_model,
                                     year: Optional[int] = None) -> QuerySet:
        """Get technologies that have facilities with both data sources.

        Args:
            technologies_model: Technologies model class
            facilities_model: facilities model class
            scada_model: FacilityScada model class
            supply_model: supplyfactors model class
            year: Optional year to check

        Returns:
            QuerySet of technologies with comparable facilities
        """
        comparable_facilities = self.get_comparable_facilities(
            facilities_model, scada_model, supply_model, year
        )

        tech_ids = comparable_facilities.values_list(
            'idtechnologies', flat=True
        ).distinct()

        return technologies_model.objects.filter(
            idtechnologies__in=tech_ids,
            renewable=1,
            dispatchable=0
        ).order_by('technology_name')
