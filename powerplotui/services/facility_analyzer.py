# powerplot/services/facility_analyzer.py
from django.db.models import Q
from siren_web.models import Technologies, facilities
from siren_web.services.facility_scada_matrix import facility_trace_for_datetime_range
from datetime import timezone as dt_timezone
import numpy as np
import logging

logger = logging.getLogger(__name__)

class FacilityAnalyzer:
    """Analyze individual facility behavior"""
    
    def analyze_facility_behavior(self, facility_code, start_date, end_date):
        """
        Analyze a specific facility's generation/consumption pattern
        
        Returns dict with:
        - total_positive_mwh: Total generation
        - total_negative_mwh: Total consumption
        - net_mwh: Net contribution
        - avg_positive_mw: Average generation when generating
        - avg_negative_mw: Average consumption when consuming
        - positive_intervals: Count of intervals generating
        - negative_intervals: Count of intervals consuming
        """
        try:
            facility_id = facilities.objects.get(facility_code=facility_code).idfacilities
        except facilities.DoesNotExist:
            return None

        start_utc = start_date if start_date.tzinfo else start_date.replace(tzinfo=dt_timezone.utc)
        end_utc = end_date if end_date.tzinfo else end_date.replace(tzinfo=dt_timezone.utc)
        trace = facility_trace_for_datetime_range(start_utc, end_utc, facility_id)

        present = trace[~np.isnan(trace)]
        if present.size == 0:
            return None

        # quantity is half-hourly ENERGY (MWh), confirmed 2026-08-19 against
        # live AEMO data (see compute_annual_demand_actuals.py's module
        # docstring). Average/max MW for a half-hourly interval = MWh / 0.5h.
        positive = present[present > 0]
        negative = present[present < 0]
        zero = present[present == 0]

        analysis = {
            'facility_code': facility_code,
            'start_date': start_date,
            'end_date': end_date,
            'total_intervals': present.size,

            # Generation (positive)
            'generation_intervals': positive.size,
            'total_generation_mwh': float(positive.sum()) if positive.size else 0,
            'avg_generation_mw': float((positive * 2).mean()) if positive.size else 0,
            'max_generation_mw': float((positive * 2).max()) if positive.size else 0,

            # Consumption (negative)
            'consumption_intervals': negative.size,
            'total_consumption_mwh': abs(float(negative.sum())) if negative.size else 0,
            'avg_consumption_mw': abs(float((negative * 2).mean())) if negative.size else 0,
            'max_consumption_mw': abs(float((negative * 2).min())) if negative.size else 0,

            # Offline/Zero
            'zero_intervals': zero.size,

            # Net contribution
            'net_energy_mwh': float(present.sum()),
        }
        
        # Calculate percentages
        analysis['generation_percentage'] = (analysis['generation_intervals'] / analysis['total_intervals']) * 100
        analysis['consumption_percentage'] = (analysis['consumption_intervals'] / analysis['total_intervals']) * 100
        analysis['offline_percentage'] = (analysis['zero_intervals'] / analysis['total_intervals']) * 100
        
        # For batteries, calculate round-trip efficiency
        if analysis['consumption_intervals'] > 0 and analysis['generation_intervals'] > 0:
            analysis['round_trip_efficiency'] = (
                analysis['total_generation_mwh'] / analysis['total_consumption_mwh'] * 100
            )
        
        return analysis
    
    def get_battery_facilities(self):
        """
        Get list of all battery facilities
        
        Returns facility codes for all battery energy storage systems (BESS).
        Uses Technologies model to identify battery facilities.
        """
        # Get battery technology IDs - looking for fuel_type containing battery-related terms
        # or technology names that indicate battery storage
        battery_tech_ids = Technologies.objects.filter(
            Q(fuel_type__icontains='battery') | 
            Q(fuel_type__icontains='bess') |
            Q(technology_name__icontains='battery') |
            Q(technology_name__icontains='bess')
        ).values_list('idtechnologies', flat=True)
        
        # Get facility codes for facilities with battery technologies
        return facilities.objects.filter(
            idtechnologies__in=battery_tech_ids
        ).values_list('facility_code', flat=True)
    
    def analyze_all_batteries(self, start_date, end_date):
        """Analyze all battery facilities"""
        batteries = self.get_battery_facilities()
        results = []
        
        for battery_code in batteries:
            analysis = self.analyze_facility_behavior(battery_code, start_date, end_date)
            if analysis:
                results.append(analysis)
        
        return results