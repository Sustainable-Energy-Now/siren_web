# powerplot/services/load_analyzer.py
from django.db.models import Sum, Avg, F, Q
from datetime import datetime, timedelta
from decimal import Decimal
from siren_web.models import FacilityScada, LoadAnalysisSummary, DPVGeneration
from siren_web.models import facilities
import pandas as pd
import logging

logger = logging.getLogger(__name__)

class LoadAnalyzer:
    
    def calculate_monthly_summary(self, year, month):
        """Calculate monthly load analysis including DPV data"""
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month + 1, 1)
        
        # Get all SCADA data for the month with facility information
        scada_data = FacilityScada.objects.filter(
            dispatch_interval__gte=start_date,
            dispatch_interval__lt=end_date
        ).select_related('facility', 'facility__idtechnologies')
        
        # Get DPV data for the month
        dpv_data = DPVGeneration.objects.filter(
            trading_date__gte=start_date.date(),
            trading_date__lt=end_date.date()
        )
        
        if not scada_data.exists():
            logger.warning(f"No SCADA data found for {year}-{month:02d}")
            return None
        
        # Convert to DataFrame with corrected field names
        scada_df = pd.DataFrame(scada_data.values(
            'dispatch_interval',
            'facility__facility_code',
            'facility__idtechnologies__technology_name',  # Corrected field name
            'quantity'
        ))
        
        # Rename columns for easier access
        scada_df.rename(columns={
            'facility__facility_code': 'facility_code',
            'facility__idtechnologies__technology_name': 'technology_name'  # Corrected
        }, inplace=True)
        
        dpv_df = pd.DataFrame(dpv_data.values(
            'trading_interval', 'estimated_generation'
        )) if dpv_data.exists() else pd.DataFrame()
        
        # Categorize generation by fuel type
        scada_df['fuel_type'] = scada_df['technology_name'].apply(self._categorize_technology)
        scada_df['is_renewable'] = scada_df['fuel_type'].isin(['WIND', 'SOLAR', 'HYDRO', 'BIOMASS'])
        scada_df['is_battery'] = scada_df['fuel_type'] == 'BATTERY'
        
        # Convert 5-min intervals to energy (MWh)
        # quantity is in MW, 5 minutes = 1/12 hour
        scada_df['energy_mwh'] = scada_df['quantity'] * Decimal('0.083333')
        
        # Process DPV data
        if not dpv_df.empty:
            dpv_df['trading_interval'] = pd.to_datetime(dpv_df['trading_interval'])
            
            # Check if post-reform (5-min) or pre-reform (30-min)
            if start_date >= datetime(2023, 10, 1):
                # 5-minute intervals
                dpv_df['energy_mwh'] = dpv_df['estimated_generation'] * Decimal('0.083333')
            else:
                # 30-minute intervals
                dpv_df['energy_mwh'] = dpv_df['estimated_generation'] * Decimal('0.5')
            
            total_dpv_generation = float(dpv_df['energy_mwh'].sum())
        else:
            logger.warning(f"No DPV data found for {year}-{month:02d}")
            total_dpv_generation = 0
        
        # Calculate key metrics
        total_re_generation = float(scada_df[scada_df['is_renewable']]['energy_mwh'].sum())
        total_wind = float(scada_df[scada_df['fuel_type'] == 'WIND']['energy_mwh'].sum())
        total_solar = float(scada_df[scada_df['fuel_type'] == 'SOLAR']['energy_mwh'].sum())
        
        total_battery_discharge = float(scada_df[
            (scada_df['is_battery']) & (scada_df['quantity'] > 0)
        ]['energy_mwh'].sum())
        
        total_battery_charge = abs(float(scada_df[
            (scada_df['is_battery']) & (scada_df['quantity'] < 0)
        ]['energy_mwh'].sum()))
        
        total_fossil = float(scada_df[
            ~scada_df['is_renewable'] & ~scada_df['is_battery']
        ]['energy_mwh'].sum())
        
        # Operational demand = total generation - battery charging
        total_generation = float(scada_df['energy_mwh'].sum())
        operational_demand_mwh = total_generation - total_battery_charge
        operational_demand_gwh = operational_demand_mwh / 1000
        
        # Underlying demand = operational + DPV
        underlying_demand_mwh = operational_demand_mwh + total_dpv_generation
        underlying_demand_gwh = underlying_demand_mwh / 1000
        
        # Total RE including DPV
        total_re_with_dpv = total_re_generation + total_dpv_generation
        
        # Calculate percentages
        re_pct_operational = (
            (total_re_generation / operational_demand_mwh) * 100 
            if operational_demand_mwh > 0 else 0
        )
        
        re_pct_underlying = (
            (total_re_with_dpv / underlying_demand_mwh) * 100
            if underlying_demand_mwh > 0 else 0
        )
        
        dpv_pct_underlying = (
            (total_dpv_generation / underlying_demand_mwh) * 100
            if underlying_demand_mwh > 0 else 0
        )
        
        bess_pct_operational = (
            (total_battery_discharge / operational_demand_mwh) * 100
            if operational_demand_mwh > 0 else 0
        )
        
        # Create or update summary
        summary, created = LoadAnalysisSummary.objects.update_or_create(
            period_date=start_date.date(),
            period_type='MONTHLY',
            defaults={
                'operational_demand': Decimal(str(operational_demand_gwh)),
                'underlying_demand': Decimal(str(underlying_demand_gwh)),
                'dpv_generation': Decimal(str(total_dpv_generation / 1000)),
                'wind_generation': Decimal(str(total_wind / 1000)),
                'solar_generation': Decimal(str(total_solar / 1000)),
                'battery_discharge': Decimal(str(total_battery_discharge / 1000)),
                'battery_charge': Decimal(str(total_battery_charge / 1000)),
                'fossil_generation': Decimal(str(total_fossil / 1000)),
                're_percentage_operational': Decimal(str(round(re_pct_operational, 2))),
                're_percentage_underlying': Decimal(str(round(re_pct_underlying, 2))),
                'dpv_percentage_underlying': Decimal(str(round(dpv_pct_underlying, 2))),
            }
        )
        
        action = "Created" if created else "Updated"
        logger.info(f"{action} monthly summary for {year}-{month:02d}")
        logger.info(
            f"Summary: Operational {operational_demand_gwh:.1f} GWh, "
            f"RE {re_pct_operational:.1f}%, DPV {dpv_pct_underlying:.1f}%"
        )
        
        return summary
    
    def _categorize_technology(self, tech_name):
        """
        Categorize technology name into fuel type
        
        Args:
            tech_name: technology_name from Technologies model
        
        Returns:
            str: fuel type category
        """
        if not tech_name:
            return 'OTHER'
        
        tech_lower = str(tech_name).lower()
        
        # Wind
        if 'wind' in tech_lower:
            return 'WIND'
        
        # Solar
        if 'solar' in tech_lower or 'pv' in tech_lower or 'photovoltaic' in tech_lower:
            return 'SOLAR'
        
        # Battery
        if 'battery' in tech_lower or 'bess' in tech_lower or 'storage' in tech_lower:
            return 'BATTERY'
        
        # Gas
        if any(term in tech_lower for term in ['gas', 'ccgt', 'ocgt', 'cogen', 'lng']):
            return 'GAS'
        
        # Coal
        if 'coal' in tech_lower:
            return 'COAL'
        
        # Hydro
        if 'hydro' in tech_lower:
            return 'HYDRO'
        
        # Biomass
        if 'biomass' in tech_lower or 'biogas' in tech_lower or 'landfill' in tech_lower:
            return 'BIOMASS'
        
        # Diesel
        if 'diesel' in tech_lower:
            return 'DIESEL'
        
        return 'OTHER'
    
    # powerplotui/services/load_analyzer.py (updated methods)

from django.db.models import Avg, Sum, Count
from django.db.models.functions import ExtractHour, ExtractMinute
import logging

logger = logging.getLogger(__name__)

class LoadAnalyzer:
    
    # ... (keep existing calculate_monthly_summary and other methods) ...
    
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
        logger.info(f"Calculating diurnal profile from {start_date} to {end_date}")
        
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
        
        logger.info(f"Aggregated {len(operational_profile)} SCADA time points")
        
        # Aggregate DPV data by time of day
        dpv_aggregated = DPVGeneration.objects.filter(
            trading_date__gte=start_date.date(),
            trading_date__lt=end_date.date()
        ).annotate(
            hour=ExtractHour('trading_interval'),
            minute=ExtractMinute('trading_interval')
        ).values('hour', 'minute').annotate(
            avg_generation=Avg('estimated_generation')
        ).order_by('hour', 'minute')
        
        # Convert to dict keyed by time_of_day
        dpv_profile = {}
        for item in dpv_aggregated:
            time_of_day = item['hour'] + item['minute'] / 60.0
            dpv_profile[time_of_day] = float(item['avg_generation'] or 0)
        
        logger.info(f"Aggregated {len(dpv_profile)} DPV time points")
        
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
        
        logger.info(f"Generated diurnal profile with {len(result)} time points")
        return result