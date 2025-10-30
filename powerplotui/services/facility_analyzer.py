# powerplot/services/facility_analyzer.py
from django.db.models import Sum, Avg, Count, Q
from siren_web.models import FacilityScada, Technologies, facilities
from datetime import datetime, timedelta
import pandas as pd
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
        data = FacilityScada.objects.filter(
            facility_code=facility_code,
            dispatch_interval__gte=start_date,
            dispatch_interval__lt=end_date
        ).order_by('dispatch_interval')
        
        if not data.exists():
            return None
        
        df = pd.DataFrame(data.values('dispatch_interval', 'quantity'))
        
        # Convert to energy (5-min intervals)
        df['energy_mwh'] = df['quantity'] * 0.083333
        
        # Separate positive and negative
        positive_df = df[df['quantity'] > 0]
        negative_df = df[df['quantity'] < 0]
        zero_df = df[df['quantity'] == 0]
        
        analysis = {
            'facility_code': facility_code,
            'start_date': start_date,
            'end_date': end_date,
            'total_intervals': len(df),
            
            # Generation (positive)
            'generation_intervals': len(positive_df),
            'total_generation_mwh': float(positive_df['energy_mwh'].sum()) if len(positive_df) > 0 else 0,
            'avg_generation_mw': float(positive_df['quantity'].mean()) if len(positive_df) > 0 else 0,
            'max_generation_mw': float(positive_df['quantity'].max()) if len(positive_df) > 0 else 0,
            
            # Consumption (negative)
            'consumption_intervals': len(negative_df),
            'total_consumption_mwh': abs(float(negative_df['energy_mwh'].sum())) if len(negative_df) > 0 else 0,
            'avg_consumption_mw': abs(float(negative_df['quantity'].mean())) if len(negative_df) > 0 else 0,
            'max_consumption_mw': abs(float(negative_df['quantity'].min())) if len(negative_df) > 0 else 0,
            
            # Offline/Zero
            'zero_intervals': len(zero_df),
            
            # Net contribution
            'net_energy_mwh': float(df['energy_mwh'].sum()),
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