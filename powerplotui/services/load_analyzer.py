# powerplot/services/load_analyzer.py
from django.db.models import Avg, F, Q
from datetime import datetime
import numpy as np
from siren_web.models import FacilityScada
from siren_web.services.dpv_matrix import values_for_date_range
from django.db.models.functions import ExtractHour, ExtractMinute
import logging

logger = logging.getLogger(__name__)


class LoadAnalyzer:
    """
    Service for analyzing load/demand data and calculating diurnal profiles.

    Note: Monthly summary data is now stored in MonthlyREPerformance model,
    populated by the update_ret_dashboard management command.
    """

    def get_diurnal_profile(self, year, month):
        """Calculate average diurnal profile including DPV - memory efficient"""
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month + 1, 1)
        
        return self._calculate_diurnal_for_range(start_date, end_date)
    
    def get_diurnal_profile_ytd(self, year, month):
        """Calculate YTD average diurnal profile - memory efficient"""
        start_date = datetime(year, 1, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month + 1, 1)
        
        return self._calculate_diurnal_for_range(start_date, end_date)
    
    def _calculate_diurnal_for_range(self, start_date, end_date):
        """
        Helper method to calculate diurnal profile for any date range
        Uses database-level aggregation to avoid memory issues
        """
        # Use database aggregation instead of loading all data into pandas
        # This groups by hour and minute, then averages across all days
        from django.db.models import F, FloatField
        from django.db.models.functions import Cast
        
        # Aggregate SCADA data by time of day
        scada_aggregated = FacilityScada.objects.filter(
            dispatch_interval__gte=start_date,
            dispatch_interval__lt=end_date
        ).annotate(
            hour=ExtractHour('dispatch_interval'),
            minute=ExtractMinute('dispatch_interval')
        ).values('hour', 'minute').annotate(
            avg_quantity=Avg('quantity')
        ).order_by('hour', 'minute')
        
        # Convert to dict keyed by time_of_day
        operational_profile = {}
        for item in scada_aggregated:
            time_of_day = item['hour'] + item['minute'] / 60.0
            operational_profile[time_of_day] = float(item['avg_quantity'] or 0)

        # Aggregate DPV data by time of day: pull the range's half-hourly
        # values out of DPVGenerationMatrix, reshape to (days, 48), and
        # average down the days axis (NaN gaps are ignored, like Avg() only
        # averaging existing rows).
        dpv_values = values_for_date_range(start_date.date(), end_date.date())
        dpv_profile = {}
        if dpv_values.size:
            n_days = dpv_values.shape[0] // 48
            with np.errstate(invalid='ignore'):
                interval_avg = np.nanmean(dpv_values[:n_days * 48].reshape(n_days, 48), axis=0)
            interval_avg = np.nan_to_num(interval_avg, nan=0.0)
            for i, avg_generation in enumerate(interval_avg):
                dpv_profile[i * 0.5] = float(avg_generation)
        
        # Combine profiles
        all_times = sorted(set(operational_profile.keys()) | set(dpv_profile.keys()))
        
        result = []
        for time_of_day in all_times:
            operational = operational_profile.get(time_of_day, 0)
            dpv = dpv_profile.get(time_of_day, 0)
            underlying = operational + dpv
            
            result.append({
                'time_of_day': float(time_of_day),
                'operational_demand': float(operational),
                'dpv_generation': float(dpv),
                'underlying_demand': float(underlying)
            })
        
        return result