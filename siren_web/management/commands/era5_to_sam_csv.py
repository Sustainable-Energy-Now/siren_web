#!/usr/bin/env python3
"""
Django Management Command for converting ERA5 NetCDF data to SAM CSV format

Converts ERA5 reanalysis data to official NREL System Adviser Model (SAM) CSV format
for solar and wind resource analysis.

Usage:
python manage.py era5_to_sam_csv --input-file=era5_data_2025_01.nc --resource-type=solar --year=2025
"""

import os
import numpy as np
import math
from datetime import datetime, timedelta
from netCDF4 import Dataset
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Convert ERA5 NetCDF data to SAM CSV format for solar and wind resources'

    def add_arguments(self, parser):
        parser.add_argument(
            '--input-file',
            type=str,
            required=True,
            help='Path to ERA5 NetCDF file'
        )

        parser.add_argument(
            '--output-dir',
            type=str,
            required=True,
            help='Directory to save SAM CSV files'
        )

        parser.add_argument(
            '--resource-type',
            type=str,
            required=True,
            choices=['solar', 'wind'],
            help='Type of resource file to create (solar or wind)'
        )

        parser.add_argument(
            '--coordinates',
            type=str,
            help='Specific lat,lon to process (e.g., "-31.95,115.86"). If omitted, processes all grid points.'
        )

        parser.add_argument(
            '--year',
            type=int,
            required=True,
            help='Year of the data'
        )

        parser.add_argument(
            '--timezone',
            type=int,
            default=8,
            help='Timezone offset from UTC in hours (default: 8 for AWST)'
        )

    def handle(self, *args, **options):
        self.options = options
        self.year = options['year']
        self.timezone = options['timezone']
        self.resource_type = options['resource_type']

        # Create output directory
        if not os.path.exists(options['output_dir']):
            os.makedirs(options['output_dir'])
            self.stdout.write(f'Created output directory: {options["output_dir"]}')

        # Load ERA5 NetCDF file
        self.load_era5_data()

        # Process based on coordinates
        if options['coordinates']:
            lat, lon = map(float, options['coordinates'].split(','))
            self.process_location(lat, lon)
        else:
            self.process_all_locations()

    def load_era5_data(self):
        """Load ERA5 NetCDF data"""
        input_file = self.options['input_file']

        if not os.path.exists(input_file):
            raise CommandError(f'Input file not found: {input_file}')

        self.stdout.write(f'Loading ERA5 data from {input_file}...')

        try:
            self.nc = Dataset(input_file, 'r')

            # Load coordinates
            self.lats = self.nc.variables['latitude'][:]
            self.lons = self.nc.variables['longitude'][:]

            # Load time
            time_var = self.nc.variables['time']
            time_units = time_var.units
            time_calendar = getattr(time_var, 'calendar', 'standard')

            # Convert time to datetime objects
            from netCDF4 import num2date
            self.times = num2date(time_var[:], units=time_units, calendar=time_calendar)

            self.stdout.write(f'  Latitude range: {self.lats.min():.2f} to {self.lats.max():.2f}')
            self.stdout.write(f'  Longitude range: {self.lons.min():.2f} to {self.lons.max():.2f}')
            self.stdout.write(f'  Time steps: {len(self.times)} hours')
            self.stdout.write(f'  Variables: {list(self.nc.variables.keys())}')

        except Exception as e:
            raise CommandError(f'Error loading ERA5 data: {str(e)}')

    def process_all_locations(self):
        """Process all grid points"""
        self.stdout.write(f'Processing all {len(self.lats)} x {len(self.lons)} = {len(self.lats) * len(self.lons)} grid points...')

        count = 0
        for lat in self.lats:
            for lon in self.lons:
                self.process_location(lat, lon)
                count += 1
                if count % 50 == 0:
                    self.stdout.write(f'  Processed {count} locations...')

        self.stdout.write(self.style.SUCCESS(f'Completed processing {count} locations'))

    def process_location(self, lat, lon):
        """Process a single location"""
        # Find nearest grid point
        lat_idx = np.argmin(np.abs(self.lats - lat))
        lon_idx = np.argmin(np.abs(self.lons - lon))

        actual_lat = float(self.lats[lat_idx])
        actual_lon = float(self.lons[lon_idx])

        # Extract data for this location
        if self.resource_type == 'solar':
            self.create_solar_csv(actual_lat, actual_lon, lat_idx, lon_idx)
        else:
            self.create_wind_csv(actual_lat, actual_lon, lat_idx, lon_idx)

    def create_solar_csv(self, lat, lon, lat_idx, lon_idx):
        """Create SAM CSV file for solar resources"""
        filename = f'solar_{lat:.4f}_{lon:.4f}_{self.year}.csv'
        filepath = os.path.join(self.options['output_dir'], filename)

        self.stdout.write(f'Creating solar CSV: {filename}')

        try:
            # Extract variables from NetCDF
            # Variable names may differ - handle both ERA5 and ERA5-Land naming
            var_names = list(self.nc.variables.keys())

            # GHI - Surface solar radiation downwards (accumulated)
            if 'ssrd' in var_names:
                ghi_data = self.nc.variables['ssrd'][:, lat_idx, lon_idx]
            elif 'surface_solar_radiation_downwards' in var_names:
                ghi_data = self.nc.variables['surface_solar_radiation_downwards'][:, lat_idx, lon_idx]
            else:
                self.stdout.write(self.style.WARNING(f'  Warning: GHI variable not found, using zeros'))
                ghi_data = np.zeros(len(self.times))

            # Temperature
            if 't2m' in var_names:
                temp_data = self.nc.variables['t2m'][:, lat_idx, lon_idx]
            elif '2m_temperature' in var_names:
                temp_data = self.nc.variables['2m_temperature'][:, lat_idx, lon_idx]
            else:
                self.stdout.write(self.style.WARNING(f'  Warning: Temperature variable not found, using 20°C'))
                temp_data = np.full(len(self.times), 293.15)  # 20°C in Kelvin

            # Dewpoint temperature
            if 'd2m' in var_names:
                dewpoint_data = self.nc.variables['d2m'][:, lat_idx, lon_idx]
            elif '2m_dewpoint_temperature' in var_names:
                dewpoint_data = self.nc.variables['2m_dewpoint_temperature'][:, lat_idx, lon_idx]
            else:
                # Estimate from temperature
                dewpoint_data = temp_data - 5  # Simple estimate

            # Relative humidity (optional)
            if 'r' in var_names:
                rh_data = self.nc.variables['r'][:, lat_idx, lon_idx]
            elif 'relative_humidity' in var_names:
                rh_data = self.nc.variables['relative_humidity'][:, lat_idx, lon_idx]
            else:
                rh_data = self.calculate_relative_humidity(temp_data, dewpoint_data)

            # Pressure
            if 'sp' in var_names:
                pressure_data = self.nc.variables['sp'][:, lat_idx, lon_idx]
            elif 'surface_pressure' in var_names:
                pressure_data = self.nc.variables['surface_pressure'][:, lat_idx, lon_idx]
            else:
                pressure_data = np.full(len(self.times), 101325.0)  # Standard pressure in Pa

            # Wind components
            if 'u10' in var_names and 'v10' in var_names:
                u10_data = self.nc.variables['u10'][:, lat_idx, lon_idx]
                v10_data = self.nc.variables['v10'][:, lat_idx, lon_idx]
            elif '10m_u_component_of_wind' in var_names and '10m_v_component_of_wind' in var_names:
                u10_data = self.nc.variables['10m_u_component_of_wind'][:, lat_idx, lon_idx]
                v10_data = self.nc.variables['10m_v_component_of_wind'][:, lat_idx, lon_idx]
            else:
                u10_data = np.zeros(len(self.times))
                v10_data = np.zeros(len(self.times))

            # Convert GHI from accumulated to instantaneous (J/m² to W/m²)
            # ERA5 accumulated values need to be divided by time step (3600 seconds for hourly)
            if 'ssrd' in var_names:
                # GHI is accumulated, convert to average W/m²
                ghi_wm2 = ghi_data / 3600.0  # Convert J/m² to W/m²
                # Handle negative values (can occur due to ERA5 accumulation)
                ghi_wm2 = np.maximum(ghi_wm2, 0)
            else:
                ghi_wm2 = ghi_data  # Already in W/m²

            # Calculate wind speed and direction
            wind_speed = np.sqrt(u10_data**2 + v10_data**2)
            wind_dir = (np.arctan2(-u10_data, -v10_data) * 180 / np.pi) % 360

            # Convert temperatures from Kelvin to Celsius
            temp_celsius = temp_data - 273.15
            dewpoint_celsius = dewpoint_data - 273.15

            # Convert pressure from Pa to millibar
            pressure_mbar = pressure_data / 100.0

            # Write SAM CSV file
            with open(filepath, 'w') as f:
                # Header Row 1: Location metadata
                f.write(f'Latitude,Longitude,Time zone,Elevation\n')

                # Header Row 2: Location values
                f.write(f'{lat:.4f},{lon:.4f},{self.timezone},0\n')

                # Header Row 3: Data column headers
                f.write('Year,Month,Day,Hour,Minute,GHI,DNI,DHI,Tdry,Tdew,RH,Pres,Wspd,Wdir\n')

                # Data rows
                for i, time_obj in enumerate(self.times):
                    # Calculate DNI and DHI from GHI
                    ghi_val = float(ghi_wm2[i])
                    dni_val, dhi_val = self.calculate_dni_dhi(
                        ghi_val,
                        time_obj.hour,
                        lat,
                        lon,
                        float(pressure_mbar[i])
                    )

                    # Write data row
                    f.write(f'{time_obj.year},{time_obj.month},{time_obj.day},'
                           f'{time_obj.hour},{time_obj.minute},'
                           f'{ghi_val:.1f},{dni_val:.1f},{dhi_val:.1f},'
                           f'{float(temp_celsius[i]):.1f},{float(dewpoint_celsius[i]):.1f},{float(rh_data[i]):.1f},'
                           f'{float(pressure_mbar[i]):.1f},'
                           f'{float(wind_speed[i]):.1f},{float(wind_dir[i]):.0f}\n')

            self.stdout.write(f'  Created: {filename}')

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  Error creating solar CSV: {str(e)}'))
            raise

    def create_wind_csv(self, lat, lon, lat_idx, lon_idx):
        """Create SAM CSV file for wind resources"""
        filename = f'wind_{lat:.4f}_{lon:.4f}_{self.year}.csv'
        filepath = os.path.join(self.options['output_dir'], filename)

        self.stdout.write(f'Creating wind CSV: {filename}')

        try:
            # Extract variables from NetCDF
            var_names = list(self.nc.variables.keys())

            # Temperature
            if 't2m' in var_names:
                temp_data = self.nc.variables['t2m'][:, lat_idx, lon_idx]
            elif '2m_temperature' in var_names:
                temp_data = self.nc.variables['2m_temperature'][:, lat_idx, lon_idx]
            else:
                temp_data = np.full(len(self.times), 293.15)  # 20°C in Kelvin

            # Pressure
            if 'sp' in var_names:
                pressure_data = self.nc.variables['sp'][:, lat_idx, lon_idx]
            elif 'surface_pressure' in var_names:
                pressure_data = self.nc.variables['surface_pressure'][:, lat_idx, lon_idx]
            else:
                pressure_data = np.full(len(self.times), 101325.0)  # Standard pressure in Pa

            # Wind at 10m
            if 'u10' in var_names and 'v10' in var_names:
                u10_data = self.nc.variables['u10'][:, lat_idx, lon_idx]
                v10_data = self.nc.variables['v10'][:, lat_idx, lon_idx]
            elif '10m_u_component_of_wind' in var_names and '10m_v_component_of_wind' in var_names:
                u10_data = self.nc.variables['10m_u_component_of_wind'][:, lat_idx, lon_idx]
                v10_data = self.nc.variables['10m_v_component_of_wind'][:, lat_idx, lon_idx]
            else:
                raise CommandError('Wind components at 10m not found in NetCDF file')

            # Wind at 100m (if available)
            if 'u100' in var_names and 'v100' in var_names:
                u100_data = self.nc.variables['u100'][:, lat_idx, lon_idx]
                v100_data = self.nc.variables['v100'][:, lat_idx, lon_idx]
            elif '100m_u_component_of_wind' in var_names and '100m_v_component_of_wind' in var_names:
                u100_data = self.nc.variables['100m_u_component_of_wind'][:, lat_idx, lon_idx]
                v100_data = self.nc.variables['100m_v_component_of_wind'][:, lat_idx, lon_idx]
            else:
                # Extrapolate from 10m using power law
                self.stdout.write('  Wind at 100m not found, extrapolating from 10m using power law')
                u100_data = u10_data * (100.0 / 10.0) ** 0.14
                v100_data = v10_data * (100.0 / 10.0) ** 0.14

            # Calculate wind speed and direction at 10m
            speed_10m = np.sqrt(u10_data**2 + v10_data**2)
            dir_10m = (np.arctan2(-u10_data, -v10_data) * 180 / np.pi) % 360

            # Calculate wind speed and direction at 100m
            speed_100m = np.sqrt(u100_data**2 + v100_data**2)
            dir_100m = (np.arctan2(-u100_data, -v100_data) * 180 / np.pi) % 360

            # Convert temperature from Kelvin to Celsius
            temp_celsius = temp_data - 273.15

            # Convert pressure from Pa to atm (SAM wind accepts atm or Pa)
            # Using atm for compatibility: 1 atm = 101325 Pa
            pressure_atm = pressure_data / 101325.0

            # Write SAM CSV file for wind
            with open(filepath, 'w') as f:
                # Header Row 1: Location metadata
                site_name = self.get_site_name(lat, lon)
                f.write(f'SiteID,{site_name},Site Timezone,{self.timezone},Data Timezone,{self.timezone},'
                       f'Longitude,{lon:.4f},Latitude,{lat:.4f},Elevation,0\n')

                # Header Row 2: Column headers with measurement heights
                f.write('Temperature at 2m,Pressure at 0m,Speed at 10m,Direction at 10m,'
                       'Speed at 100m,Direction at 100m\n')

                # Data rows (no timestamps needed for SAM wind format)
                for i in range(len(self.times)):
                    f.write(f'{float(temp_celsius[i]):.2f},{float(pressure_atm[i]):.5f},'
                           f'{float(speed_10m[i]):.2f},{float(dir_10m[i]):.0f},'
                           f'{float(speed_100m[i]):.2f},{float(dir_100m[i]):.0f}\n')

            self.stdout.write(f'  Created: {filename}')

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  Error creating wind CSV: {str(e)}'))
            raise

    def get_site_name(self, lat, lon):
        """Generate a descriptive site name based on location"""
        # Approximate location names for SWIS region
        if -28.5 < lat < -27.5 and 114 < lon < 115:
            return "Geraldton"
        elif -32.5 < lat < -31.5 and 115.5 < lon < 116.5:
            return "Perth"
        elif -33.5 < lat < -32.5 and 115 < lon < 116:
            return "Bunbury"
        elif -33.5 < lat < -32.5 and 114 < lon < 115.5:
            return "Offshore Kemerton"
        elif -35.5 < lat < -34.5 and 117 < lon < 118:
            return "Albany"
        else:
            return f"SWIS_{lat:.2f}_{lon:.2f}"

    def calculate_dni_dhi(self, ghi, hour, lat, lon, pressure):
        """
        Calculate DNI and DHI from GHI using simplified DISC model

        Based on Maxwell (1987) DISC model for separating direct and diffuse irradiance
        """
        if ghi <= 0:
            return 0.0, 0.0

        # Calculate solar position
        solar_elevation = self.solar_elevation_angle(hour, lat, lon)

        if solar_elevation <= 0:
            # Sun is below horizon
            return 0.0, 0.0

        # Calculate extraterrestrial radiation
        day_of_year = self.get_day_of_year()
        I0 = 1367.0  # Solar constant W/m²

        # Earth-sun distance correction
        B = 2 * np.pi * (day_of_year - 1) / 365
        earth_sun_dist = 1.00011 + 0.034221 * np.cos(B) + 0.00128 * np.sin(B)
        I0_corrected = I0 * earth_sun_dist

        # Extraterrestrial radiation on horizontal surface
        I0h = I0_corrected * np.sin(np.radians(solar_elevation))

        if I0h <= 0:
            return 0.0, 0.0

        # Clearness index
        kt = ghi / I0h
        kt = min(kt, 1.0)  # Cap at 1.0

        # DISC model coefficients (simplified)
        if kt < 0.3:
            kn = 0.5 - 0.8 * kt
        elif kt < 0.78:
            kn = 1.0 - 2.0 * (1.0 - kt)
        else:
            kn = 0.2

        # DNI calculation
        dni = kn * I0_corrected

        # DHI calculation
        dhi = ghi - dni * np.sin(np.radians(solar_elevation))
        dhi = max(dhi, 0.0)

        # Ensure DNI is reasonable
        dni = min(dni, 1000.0)

        return dni, dhi

    def solar_elevation_angle(self, hour, lat, lon):
        """
        Calculate solar elevation angle (altitude) in degrees

        Simplified calculation for the given hour
        """
        day_of_year = self.get_day_of_year()

        # Solar declination (degrees)
        declination = 23.45 * np.sin(np.radians((360.0 / 365.0) * (day_of_year - 81)))

        # Hour angle (degrees)
        # Assuming hour is in UTC, adjust for longitude
        solar_noon = 12.0 - lon / 15.0  # Approximate solar noon in UTC
        hour_angle = 15.0 * (hour - solar_noon)

        # Solar elevation
        lat_rad = np.radians(lat)
        dec_rad = np.radians(declination)
        hour_rad = np.radians(hour_angle)

        elevation = np.degrees(np.arcsin(
            np.sin(lat_rad) * np.sin(dec_rad) +
            np.cos(lat_rad) * np.cos(dec_rad) * np.cos(hour_rad)
        ))

        return max(elevation, 0.0)

    def get_day_of_year(self):
        """Get day of year (1-365)"""
        # Use middle of the dataset
        mid_idx = len(self.times) // 2
        if mid_idx < len(self.times):
            date = self.times[mid_idx]
            return date.timetuple().tm_yday
        return 1

    def calculate_relative_humidity(self, temp_kelvin, dewpoint_kelvin):
        """Calculate relative humidity from temperature and dewpoint"""
        # Magnus formula for saturation vapor pressure
        def es(T_celsius):
            return 6.112 * np.exp((17.67 * T_celsius) / (T_celsius + 243.5))

        T_celsius = temp_kelvin - 273.15
        Td_celsius = dewpoint_kelvin - 273.15

        rh = 100.0 * (es(Td_celsius) / es(T_celsius))
        rh = np.clip(rh, 0, 100)

        return rh

    def __del__(self):
        """Close NetCDF file when done"""
        if hasattr(self, 'nc'):
            self.nc.close()