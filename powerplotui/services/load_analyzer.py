# powerplot/services/load_analyzer.py (updated)
from django.db.models import Sum, Avg, F, Q
from datetime import datetime, timedelta
from decimal import Decimal
from siren_web.models import FacilityScada, FacilityMetadata, LoadAnalysisSummary, DPVGeneration
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

        # Get SCADA data with facility information
        scada_data = FacilityScada.objects.filter(
            dispatch_interval__gte=start_date,
            dispatch_interval__lt=end_date
        ).select_related('facility', 'facility__idtechnologies')
        
        if not scada_data.exists():
            logger.warning(f"No SCADA data found for {year}-{month:02d}")
            return None
        
        # Convert to DataFrame
        scada_df = pd.DataFrame(scada_data.values(
            'dispatch_interval',
            'facility__facility_code',
            'facility__idtechnologies__technology',
            'quantity'
        ))
        
        # Rename columns for easier access
        scada_df.rename(columns={
            'facility__facility_code': 'facility_code',
            'facility__idtechnologies__technology': 'fuel_type'
        }, inplace=True)
        
        # Get DPV data for the month
        dpv_data = DPVGeneration.objects.filter(
            trading_date__gte=start_date.date(),
            trading_date__lt=end_date.date()
        )
        
        if not scada_data.exists():
            logger.warning(f"No SCADA data found for {year}-{month:02d}")
            return None
        
        # Convert to DataFrames
        scada_df = pd.DataFrame(scada_data.values(
            'dispatch_interval', 'facility_code', 'quantity'
        ))
        
        dpv_df = pd.DataFrame(dpv_data.values(
            'trading_interval', 'estimated_generation'
        )) if dpv_data.exists() else pd.DataFrame()
        
        # Get facility metadata
        facilities = FacilityMetadata.objects.all()
        facility_map = {f.code: f for f in facilities}
        
        # Categorize generation
        scada_df['fuel_type'] = scada_df['facility_code'].map(
            lambda x: facility_map[x].fuel_type if x in facility_map else 'OTHER'
        )
        scada_df['is_renewable'] = scada_df['facility_code'].map(
            lambda x: facility_map[x].is_renewable if x in facility_map else False
        )
        scada_df['is_battery'] = scada_df['fuel_type'] == 'BATTERY'
        
        # Convert 5-min intervals to energy (MWh)
        # quantity is in MW, 5 minutes = 1/12 hour
        scada_df['energy_mwh'] = scada_df['quantity'] * Decimal('0.083333')
        
        # Process DPV data
        if not dpv_df.empty:
            # Determine interval duration based on data
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
        # Positive = Discharge (generation), Negative = Charge (consumption)
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
        
        return summary
    
    def get_diurnal_profile(self, year, month):
        """Calculate average diurnal profile including DPV"""
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month + 1, 1)
        
        # Get SCADA data
        scada_data = FacilityScada.objects.filter(
            dispatch_interval__gte=start_date,
            dispatch_interval__lt=end_date
        )
        
        # Get DPV data
        dpv_data = DPVGeneration.objects.filter(
            trading_date__gte=start_date.date(),
            trading_date__lt=end_date.date()
        )
        
        scada_df = pd.DataFrame(scada_data.values())
        dpv_df = pd.DataFrame(dpv_data.values()) if dpv_data.exists() else pd.DataFrame()
        
        if scada_df.empty:
            return []
        
        # Process SCADA
        scada_df['datetime'] = pd.to_datetime(scada_df['dispatch_interval'])
        scada_df['hour'] = scada_df['datetime'].dt.hour
        scada_df['minute'] = scada_df['datetime'].dt.minute
        scada_df['time_of_day'] = scada_df['hour'] + scada_df['minute'] / 60
        
        # Aggregate by time of day
        operational_profile = scada_df.groupby('time_of_day')['quantity'].mean()
        
        # Process DPV if available
        if not dpv_df.empty:
            dpv_df['datetime'] = pd.to_datetime(dpv_df['trading_interval'])
            dpv_df['hour'] = dpv_df['datetime'].dt.hour
            dpv_df['minute'] = dpv_df['datetime'].dt.minute
            dpv_df['time_of_day'] = dpv_df['hour'] + dpv_df['minute'] / 60
            
            dpv_profile = dpv_df.groupby('time_of_day')['estimated_generation'].mean()
            
            # Combine for underlying demand
            underlying_profile = operational_profile.add(dpv_profile, fill_value=0)
        else:
            underlying_profile = operational_profile
        
        # Convert to list of dicts
        result = []
        for time_of_day in sorted(underlying_profile.index):
            result.append({
                'time_of_day': float(time_of_day),
                'operational_demand': float(operational_profile.get(time_of_day, 0)),
                'underlying_demand': float(underlying_profile.get(time_of_day, 0)),
                'dpv_generation': float(dpv_profile.get(time_of_day, 0)) if not dpv_df.empty else 0
            })
        
        return result