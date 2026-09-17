# powerplot/services/load_analyzer.py
from datetime import datetime, timezone as dt_timezone
import numpy as np
from siren_web.services.dpv_matrix import values_for_date_range
from siren_web.services.facility_scada_matrix import facility_matrix_for_datetime_range
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
        # Aggregate SCADA data by time of day: average every (facility, day)
        # cell sharing the same half-hourly interval-of-day, matching the
        # old Avg('quantity') grouped by hour/minute (NaN/missing cells are
        # excluded from the average, like a missing row would be).
        # start_date/end_date are naive -- Django's ORM (and this project's
        # settings.TIME_ZONE='UTC') treats a naive datetime filtered against
        # dispatch_interval as already being in UTC, so attach UTC tzinfo
        # explicitly here rather than relying on Python's own (locale-
        # dependent) naive-datetime handling.
        start_utc = start_date.replace(tzinfo=dt_timezone.utc)
        end_utc = end_date.replace(tzinfo=dt_timezone.utc)
        _, scada_matrix = facility_matrix_for_datetime_range(start_utc, end_utc)

        operational_profile = {}
        if scada_matrix.size:
            n_days = scada_matrix.shape[1] // 48
            with np.errstate(invalid='ignore'):
                interval_avg = np.nanmean(
                    scada_matrix[:, :n_days * 48].reshape(scada_matrix.shape[0], n_days, 48),
                    axis=(0, 1),
                )
            for i, avg_quantity in enumerate(interval_avg):
                time_of_day = i * 0.5
                operational_profile[time_of_day] = float(avg_quantity) if not np.isnan(avg_quantity) else 0.0

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