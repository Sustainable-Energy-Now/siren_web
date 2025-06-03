#!/usr/bin/env python3
"""
Django Management Command for processing ERA5 NetCDF files into SAM-compatible weather files
Based on makeweatherfiles.py from SIREN project

Usage:
python manage.py process_era5_grib [options]

Note: This command primarily works with NetCDF files (.nc) which are what you download from CDS.
GRIB support requires pygrib which can be difficult to install on Windows.
"""

import os
import sys
import gzip
from datetime import datetime, timedelta
from math import sqrt, atan, degrees, atan2
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
import numpy as np

try:
    from netCDF4 import Dataset
    NETCDF4_AVAILABLE = True
except ImportError:
    NETCDF4_AVAILABLE = False

try:
    import pygrib
    PYGRIB_AVAILABLE = True
except ImportError:
    PYGRIB_AVAILABLE = False


class Command(BaseCommand):
    help = 'Process ERA5 NetCDF files into SAM-compatible weather files for South West WA'

    def add_arguments(self, parser):
        parser.add_argument(
            '--input-file',
            type=str,
            required=True,
            help='Path to ERA5 NetCDF file to process (downloaded from CDS)'
        )
        
        parser.add_argument(
            '--output-dir',
            type=str,
            default=os.path.join(settings.BASE_DIR, 'weather_output'),
            help='Directory to save processed weather files'
        )
        
        parser.add_argument(
            '--format',
            type=str,
            choices=['csv', 'smw', 'srw'],
            default='csv',
            help='Output format: csv (SAM CSV), smw (solar), srw (wind)'
        )
        
        parser.add_argument(
            '--year',
            type=int,
            default=datetime.now().year - 1,
            help='Year of the data (for filename and processing)'
        )
        
        parser.add_argument(
            '--timezone',
            type=int,
            default=8,
            help='Time zone offset for South West WA (default: 8 for AWST)'
        )
        
        parser.add_argument(
            '--coordinates',
            type=str,
            help='Specific coordinates as lat1,lon1,lat2,lon2,... (if not provided, processes all locations)'
        )
        
        parser.add_argument(
            '--hub-height',
            type=int,
            default=0,
            help='Hub height for wind extrapolation (0 = no extrapolation)'
        )
        
        parser.add_argument(
            '--wind-law',
            type=str,
            choices=['logarithmic', 'hellman'],
            default='logarithmic',
            help='Wind extrapolation law'
        )

    def handle(self, *args, **options):
        # Check required libraries
        if not NETCDF4_AVAILABLE:
            raise CommandError(
                'netCDF4 library is required. Install with:\n'
                'pip install netCDF4\n'
                'Note: This command works with NetCDF files (.nc) downloaded from CDS.\n'
                'For GRIB files, you would need pygrib which can be difficult to install on Windows.'
            )
        
        self.options = options
        self.input_file = options['input_file']
        self.output_dir = options['output_dir']
        self.format = options['format']
        self.year = options['year']
        self.timezone = options['timezone']
        self.hub_height = options['hub_height']
        self.wind_law = options['wind_law'][0].lower()  # 'l' or 'h'
        
        # Parse coordinates if provided
        if options['coordinates']:
            coords = options['coordinates'].replace(' ', '').split(',')
            if len(coords) % 2 != 0:
                raise CommandError('Coordinates must be pairs of lat,lon values')
            self.specific_coords = []
            for i in range(0, len(coords), 2):
                self.specific_coords.append((float(coords[i]), float(coords[i+1])))
        else:
            self.specific_coords = None
        
        # South West WA boundaries (same as ERA5 download command)
        self.boundaries = {
            'north': -28.0,
            'south': -35.0, 
            'west': 114.0,
            'east': 120.0
        }
        
        self.setup_output_directory()
        self.process_era5_file()

    def setup_output_directory(self):
        """Create output directory if it doesn't exist"""
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
            self.stdout.write(f'Created output directory: {self.output_dir}')

    def unzip_file(self, file_path):
        """Handle gzipped files"""
        if file_path.endswith('.gz'):
            if not os.path.exists(file_path):
                raise CommandError(f'File not found: {file_path}')
            
            out_file = file_path[:-3]  # Remove .gz extension
            if not os.path.exists(out_file):
                self.stdout.write(f'Unzipping {file_path}...')
                with gzip.open(file_path, 'rb') as f_in:
                    with open(out_file, 'wb') as f_out:
                        f_out.write(f_in.read())
            return out_file
        else:
            if not os.path.exists(file_path):
                raise CommandError(f'File not found: {file_path}')
            return file_path

    def detect_file_format(self, file_path):
        """Detect if file is NetCDF (GRIB support removed due to installation issues)"""
        try:
            # Try NetCDF
            if NETCDF4_AVAILABLE:
                Dataset(file_path, 'r').close()
                return 'netcdf'
        except Exception as e:
            pass
        
        # Check file extension
        if file_path.lower().endswith(('.nc', '.nc4', '.netcdf')):
            return 'netcdf'
        elif file_path.lower().endswith(('.grib', '.grib2', '.grb', '.grb2')):
            raise CommandError(
                f'GRIB file detected: {file_path}\n'
                'GRIB support requires pygrib which failed to install.\n'
                'Please convert your GRIB file to NetCDF format using:\n'
                '  cdo copy input.grib output.nc\n'
                'Or download NetCDF format directly from CDS (which is what our download command does).'
            )
        
        raise CommandError(f'Unable to detect file format for {file_path}. Expected NetCDF (.nc) file.')

    def process_era5_file(self):
        """Main processing function"""
        # Unzip if needed
        file_path = self.unzip_file(self.input_file)
        
        # Detect format
        file_format = self.detect_file_format(file_path)
        self.stdout.write(f'Processing {file_format.upper()} file: {os.path.basename(file_path)}')
        
        # Read NetCDF file
        data = self.read_netcdf_file(file_path)
        
        # Validate data
        self.validate_era5_data(data)
        
        # Process the data based on output format
        if self.format == 'srw':
            self.create_wind_files(data)
        else:
            self.create_solar_files(data)

    def read_netcdf_file(self, file_path):
        """Read ERA5 NetCDF file and extract required variables"""
        self.stdout.write('Reading NetCDF file...')
        
        try:
            with Dataset(file_path, 'r') as nc:
                # Print file info for debugging
                self.stdout.write(f'File dimensions: {list(nc.dimensions.keys())}')
                self.stdout.write(f'File variables: {list(nc.variables.keys())}')
                
                data = {
                    'lats': None,
                    'lons': None,
                    'times': [],
                    'variables': {}
                }
                
                # Handle coordinate variables (different naming conventions)
                lat_names = ['latitude', 'lat', 'y']
                lon_names = ['longitude', 'lon', 'x']
                time_names = ['time', 'valid_time', 't']
                
                # Find latitude
                lat_var_name = None
                for lat_name in lat_names:
                    if lat_name in nc.variables:
                        data['lats'] = nc.variables[lat_name][:]
                        lat_var_name = lat_name
                        self.stdout.write(f'Found latitude: {lat_name} (shape: {data["lats"].shape})')
                        break
                
                if data['lats'] is None:
                    raise CommandError(f'Could not find latitude in variables: {list(nc.variables.keys())}')
                
                # Find longitude
                lon_var_name = None
                for lon_name in lon_names:
                    if lon_name in nc.variables:
                        data['lons'] = nc.variables[lon_name][:]
                        lon_var_name = lon_name
                        self.stdout.write(f'Found longitude: {lon_name} (shape: {data["lons"].shape})')
                        break
                
                if data['lons'] is None:
                    raise CommandError(f'Could not find longitude in variables: {list(nc.variables.keys())}')
                
                # Find time variable
                time_var_name = None
                time_var = None
                for time_name in time_names:
                    if time_name in nc.variables:
                        time_var = nc.variables[time_name]
                        time_var_name = time_name
                        self.stdout.write(f'Found time: {time_name} (shape: {time_var.shape})')
                        break
                
                if time_var is None:
                    # If no explicit time variable, check dimensions for time-like names
                    for dim_name in nc.dimensions.keys():
                        if any(t_name in dim_name.lower() for t_name in ['time', 'hour']):
                            self.stdout.write(f'Using dimension as time: {dim_name}')
                            # Create time array based on dimension size
                            time_size = len(nc.dimensions[dim_name])
                            base_time = datetime(self.year, 1, 1)
                            for i in range(time_size):
                                data['times'].append(base_time + timedelta(hours=i))
                            break
                    
                    if not data['times']:
                        # Last resort: create hourly time series for the year
                        self.stdout.write('No time variable found, creating hourly series for the year')
                        base_time = datetime(self.year, 1, 1)
                        for i in range(8760):  # 365 * 24 hours
                            data['times'].append(base_time + timedelta(hours=i))
                else:
                    # Parse time variable
                    try:
                        time_units = time_var.units
                        self.stdout.write(f'Time units: {time_units}')
                        
                        # Parse reference time from units string
                        if 'since' in time_units:
                            ref_part = time_units.split('since ')[1].strip()
                            # Handle different date formats
                            for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%Y%m%d']:
                                try:
                                    base_time = datetime.strptime(ref_part.split(' ')[0], fmt)
                                    break
                                except ValueError:
                                    continue
                            else:
                                # Default fallback
                                base_time = datetime(1900, 1, 1)
                        else:
                            base_time = datetime(1900, 1, 1)
                        
                        # Convert time values to datetime objects
                        for t in time_var[:]:
                            if 'hours' in time_units:
                                time_obj = base_time + timedelta(hours=float(t))
                            elif 'seconds' in time_units:
                                time_obj = base_time + timedelta(seconds=float(t))
                            elif 'days' in time_units:
                                time_obj = base_time + timedelta(days=float(t))
                            else:
                                # Assume hours if units unclear
                                time_obj = base_time + timedelta(hours=float(t))
                            data['times'].append(time_obj)
                    
                    except Exception as e:
                        self.stdout.write(f'Error parsing time variable: {e}')
                        # Fallback: create time series
                        base_time = datetime(self.year, 1, 1)
                        time_size = len(time_var)
                        for i in range(time_size):
                            data['times'].append(base_time + timedelta(hours=i))
                
                self.stdout.write(f'Created {len(data["times"])} time steps')
                if data['times']:
                    self.stdout.write(f'Time range: {data["times"][0]} to {data["times"][-1]}')
                
                # Read variables with multiple possible names
                var_mapping = {
                    # ERA5 standard names -> our standard names
                    't2m': '2m_temperature',
                    '2t': '2m_temperature', 
                    'temperature_2m': '2m_temperature',
                    
                    'sp': 'surface_pressure',
                    'surface_pressure': 'surface_pressure',
                    'msl': 'surface_pressure',
                    
                    'ssrd': 'surface_solar_radiation_downwards',
                    'surface_solar_radiation_downwards': 'surface_solar_radiation_downwards',
                    'dsrp': 'surface_solar_radiation_downwards',
                    
                    'u10': '10m_u_component_of_wind',
                    '10m_u_component_of_wind': '10m_u_component_of_wind',
                    'u10m': '10m_u_component_of_wind',
                    
                    'v10': '10m_v_component_of_wind', 
                    '10m_v_component_of_wind': '10m_v_component_of_wind',
                    'v10m': '10m_v_component_of_wind',
                    
                    'u100': '100m_u_component_of_wind',
                    '100m_u_component_of_wind': '100m_u_component_of_wind',
                    'u100m': '100m_u_component_of_wind',
                    
                    'v100': '100m_v_component_of_wind',
                    '100m_v_component_of_wind': '100m_v_component_of_wind', 
                    'v100m': '100m_v_component_of_wind',
                    
                    'tcc': 'total_cloud_cover',
                    'total_cloud_cover': 'total_cloud_cover',
                    'cloudcover': 'total_cloud_cover'
                }
                
                # Read variables that exist in the file
                for nc_var, standard_name in var_mapping.items():
                    if nc_var in nc.variables:
                        try:
                            var_data = nc.variables[nc_var][:]
                            data['variables'][standard_name] = var_data
                            self.stdout.write(f"Read variable: {nc_var} -> {standard_name} (shape: {var_data.shape})")
                        except Exception as e:
                            self.stdout.write(f"Error reading {nc_var}: {e}")
                
                # Check for any other variables that might be useful
                for var_name in nc.variables:
                    if var_name not in [lat_var_name, lon_var_name, time_var_name]:
                        if var_name not in var_mapping:
                            try:
                                var_info = nc.variables[var_name]
                                self.stdout.write(f"Additional variable found: {var_name} {getattr(var_info, 'long_name', '')} (shape: {var_info.shape})")
                            except:
                                self.stdout.write(f"Additional variable found: {var_name}")
        
        except Exception as e:
            raise CommandError(f'Error reading NetCDF file: {str(e)}')
        
        # Validate we have minimum required data
        if not data['times']:
            raise CommandError('No time information could be extracted from file')
        
        if len(data['variables']) == 0:
            raise CommandError('No recognizable variables found in file')
        
        self.stdout.write(f"Successfully read {len(data['variables'])} variables for {len(data['times'])} time steps")
        return data

    def calculate_wind_speed_direction(self, u_data, v_data):
        """Calculate wind speed and direction from U and V components"""
        if isinstance(u_data, dict) and isinstance(v_data, dict):
            # GRIB format - data organized by time
            speed_data = {}
            direction_data = {}
            
            for time_key in u_data.keys():
                if time_key in v_data:
                    u = u_data[time_key]
                    v = v_data[time_key]
                    
                    # Calculate speed
                    speed_data[time_key] = np.sqrt(u**2 + v**2)
                    
                    # Calculate direction (meteorological convention)
                    direction = np.degrees(np.arctan2(-u, -v)) % 360
                    direction_data[time_key] = direction
            
            return speed_data, direction_data
        else:
            # NetCDF format - data as arrays
            speed_data = np.sqrt(u_data**2 + v_data**2)
            direction_data = np.degrees(np.arctan2(-u_data, -v_data)) % 360
            return speed_data, direction_data

    def convert_temperature(self, temp_data):
        """Convert temperature from Kelvin to Celsius"""
        if isinstance(temp_data, dict):
            return {k: v - 273.15 for k, v in temp_data.items()}
        else:
            return temp_data - 273.15

    def convert_pressure(self, pressure_data):
        """Convert pressure from Pa to mbar (hPa)"""
        if isinstance(pressure_data, dict):
            return {k: v / 100.0 for k, v in pressure_data.items()}
        else:
            return pressure_data / 100.0

    def interpolate_to_point(self, data, target_lat, target_lon, lats, lons):
        """Interpolate gridded data to a specific point using bilinear interpolation"""
        # Find surrounding grid points
        lat_idx = np.searchsorted(lats, target_lat)
        lon_idx = np.searchsorted(lons, target_lon)
        
        # Handle edge cases
        if lat_idx == 0:
            lat_idx = 1
        elif lat_idx >= len(lats):
            lat_idx = len(lats) - 1
            
        if lon_idx == 0:
            lon_idx = 1
        elif lon_idx >= len(lons):
            lon_idx = len(lons) - 1
        
        # Get surrounding points
        lat1, lat2 = lats[lat_idx-1], lats[lat_idx]
        lon1, lon2 = lons[lon_idx-1], lons[lon_idx]
        
        # Calculate interpolation weights
        lat_weight = (target_lat - lat1) / (lat2 - lat1) if lat2 != lat1 else 0
        lon_weight = (target_lon - lon1) / (lon2 - lon1) if lon2 != lon1 else 0
        
        # Bilinear interpolation
        if isinstance(data, dict):
            # GRIB format
            result = {}
            for time_key, values in data.items():
                v11 = values[lat_idx-1, lon_idx-1]
                v12 = values[lat_idx-1, lon_idx]
                v21 = values[lat_idx, lon_idx-1]
                v22 = values[lat_idx, lon_idx]
                
                # Bilinear interpolation
                v1 = v11 * (1 - lon_weight) + v12 * lon_weight
                v2 = v21 * (1 - lon_weight) + v22 * lon_weight
                result[time_key] = v1 * (1 - lat_weight) + v2 * lat_weight
            return result
        else:
            # NetCDF format
            result = []
            for t in range(data.shape[0]):
                v11 = data[t, lat_idx-1, lon_idx-1]
                v12 = data[t, lat_idx-1, lon_idx]
                v21 = data[t, lat_idx, lon_idx-1]
                v22 = data[t, lat_idx, lon_idx]
                
                # Bilinear interpolation
                v1 = v11 * (1 - lon_weight) + v12 * lon_weight
                v2 = v21 * (1 - lon_weight) + v22 * lon_weight
                result.append(v1 * (1 - lat_weight) + v2 * lat_weight)
            return np.array(result)

    def calculate_dni_dhi(self, ghi, hour, lat, lon, pressure):
        """Calculate DNI and DHI from GHI (simplified model)"""
        # This is a simplified model - for production use, consider more sophisticated models
        # Based on the DISC model used in the original code
        
        # Simple clear sky model for DNI estimation
        # This is a placeholder - you might want to implement a more sophisticated model
        solar_elevation = self.calculate_solar_elevation(hour, lat, lon)
        
        if solar_elevation <= 0:
            return 0.0, 0.0  # No sun
        
        # Simplified DNI calculation
        clearness_index = min(ghi / (1361 * max(0.1, solar_elevation)), 1.0)
        
        if clearness_index < 0.22:
            dni = 0.0
        else:
            dni = ghi * (1.0 - 0.09 * (1.0 - clearness_index)**2)
        
        # DHI is the remainder
        dhi = ghi - dni * max(0.1, solar_elevation)
        dhi = max(0.0, dhi)
        
        return max(0.0, dni), dhi

    def calculate_solar_elevation(self, hour, lat, lon):
        """Calculate solar elevation angle (simplified)"""
        # This is a very simplified calculation
        # For production use, consider using a proper solar position algorithm
        day_of_year = 180  # Approximate middle of year
        
        # Declination angle
        declination = 23.45 * np.sin(np.radians(360 * (284 + day_of_year) / 365))
        
        # Hour angle
        hour_angle = 15 * (hour - 12)
        
        # Solar elevation
        elevation = np.arcsin(
            np.sin(np.radians(lat)) * np.sin(np.radians(declination)) +
            np.cos(np.radians(lat)) * np.cos(np.radians(declination)) * np.cos(np.radians(hour_angle))
        )
        
        return max(0.0, np.degrees(elevation) / 90.0)  # Normalized to 0-1

    def extrapolate_wind(self, wind_speed, from_height, to_height):
        """Extrapolate wind speed to different height"""
        if self.wind_law == 'h':
            # Hellman exponential law
            alpha = 0.143  # Typical value for open terrain
            return wind_speed * (to_height / from_height) ** alpha
        else:
            # Logarithmic law
            z0 = 0.1  # Roughness length for open terrain
            return wind_speed * np.log(to_height / z0) / np.log(from_height / z0)

    def create_wind_files(self, data):
        """Create wind weather files (.srw format)"""
        self.stdout.write('Creating wind weather files...')
        
        # Required variables for wind files
        required_vars = ['2m_temperature', 'surface_pressure', '10m_u_component_of_wind', 
                        '10m_v_component_of_wind', '100m_u_component_of_wind', '100m_v_component_of_wind']
        
        missing_vars = [var for var in required_vars if var not in data['variables']]
        if missing_vars:
            self.stdout.write(f"Warning: Missing variables: {missing_vars}")
        
        # Calculate wind speeds and directions
        if '10m_u_component_of_wind' in data['variables'] and '10m_v_component_of_wind' in data['variables']:
            speed_10m, direction_10m = self.calculate_wind_speed_direction(
                data['variables']['10m_u_component_of_wind'],
                data['variables']['10m_v_component_of_wind']
            )
        
        if '100m_u_component_of_wind' in data['variables'] and '100m_v_component_of_wind' in data['variables']:
            speed_100m, direction_100m = self.calculate_wind_speed_direction(
                data['variables']['100m_u_component_of_wind'],
                data['variables']['100m_v_component_of_wind']
            )
        
        # Convert temperature and pressure
        temperature = self.convert_temperature(data['variables']['2m_temperature'])
        pressure = self.convert_pressure(data['variables']['surface_pressure'])
        
        # Create files for specific coordinates or all grid points
        if self.specific_coords:
            for lat, lon in self.specific_coords:
                self.create_wind_file_for_point(
                    lat, lon, data['times'], data['lats'], data['lons'],
                    temperature, pressure, speed_10m, direction_10m, speed_100m, direction_100m
                )
        else:
            self.stdout.write("Processing all grid points (this may take a while)...")
            for i, lat in enumerate(data['lats']):
                for j, lon in enumerate(data['lons']):
                    if self.boundaries['south'] <= lat <= self.boundaries['north'] and \
                       self.boundaries['west'] <= lon <= self.boundaries['east']:
                        self.create_wind_file_for_point(
                            lat, lon, data['times'], data['lats'], data['lons'],
                            temperature, pressure, speed_10m, direction_10m, speed_100m, direction_100m,
                            grid_indices=(i, j)
                        )

    def create_wind_file_for_point(self, lat, lon, times, lats, lons, temperature, pressure,
                                  speed_10m, direction_10m, speed_100m, direction_100m, grid_indices=None):
        """Create wind file for a specific point"""
        
        filename = f'wind_weather_{lat:.4f}_{lon:.4f}_{self.year}.srw'
        filepath = os.path.join(self.output_dir, filename)
        
        with open(filepath, 'w') as f:
            # Header
            f.write(f'id,<city>,<state>,<country>,{self.year},{lat:.4f},{lon:.4f},0,1,8760\n')
            f.write('Wind data derived from ERA5 reanalysis-era5-single-levels\n')
            f.write('Temperature,Pressure,Direction,Speed,Direction,Speed\n')
            f.write('C,atm,degrees,m/s,degrees,m/s\n')
            f.write('2,0,10,10,100,100\n')
            
            # Data
            for time_obj in times:
                if grid_indices:
                    i, j = grid_indices
                    # Direct grid access
                    if isinstance(temperature, dict):
                        temp = temperature[time_obj][i, j]
                        press = pressure[time_obj][i, j] / 101325  # Convert to atm
                        speed_10 = speed_10m[time_obj][i, j]
                        dir_10 = direction_10m[time_obj][i, j]
                        speed_100 = speed_100m[time_obj][i, j]
                        dir_100 = direction_100m[time_obj][i, j]
                    else:
                        # NetCDF format - find time index
                        time_idx = times.index(time_obj)
                        temp = temperature[time_idx, i, j]
                        press = pressure[time_idx, i, j] / 101325
                        speed_10 = speed_10m[time_idx, i, j]
                        dir_10 = direction_10m[time_idx, i, j]
                        speed_100 = speed_100m[time_idx, i, j]
                        dir_100 = direction_100m[time_idx, i, j]
                else:
                    # Interpolate to point
                    temp = self.interpolate_to_point(temperature, lat, lon, lats, lons)
                    press = self.interpolate_to_point(pressure, lat, lon, lats, lons)
                    speed_10 = self.interpolate_to_point(speed_10m, lat, lon, lats, lons)
                    dir_10 = self.interpolate_to_point(direction_10m, lat, lon, lats, lons)
                    speed_100 = self.interpolate_to_point(speed_100m, lat, lon, lats, lons)
                    dir_100 = self.interpolate_to_point(direction_100m, lat, lon, lats, lons)
                    
                    if isinstance(temp, dict):
                        temp = temp[time_obj]
                        press = press[time_obj] / 101325
                        speed_10 = speed_10[time_obj]
                        dir_10 = dir_10[time_obj]
                        speed_100 = speed_100[time_obj]
                        dir_100 = dir_100[time_obj]
                    else:
                        time_idx = times.index(time_obj)
                        temp = temp[time_idx]
                        press = press[time_idx] / 101325
                        speed_10 = speed_10[time_idx]
                        dir_10 = dir_10[time_idx]
                        speed_100 = speed_100[time_idx]
                        dir_100 = dir_100[time_idx]
                
                # Apply hub height extrapolation if needed
                if self.hub_height > 100:
                    speed_100 = self.extrapolate_wind(speed_100, 100, self.hub_height)
                
                f.write(f'{temp:.1f},{press:.6f},{dir_10:.0f},{speed_10:.4f},{dir_100:.0f},{speed_100:.4f}\n')
        
        self.stdout.write(f'Created: {filename}')

    def create_solar_files(self, data):
        """Create solar weather files (.csv or .smw format)"""
        self.stdout.write('Creating solar weather files...')
        
        # Required variables
        required_vars = ['surface_solar_radiation_downwards']
        
        missing_vars = [var for var in required_vars if var not in data['variables']]
        if missing_vars:
            self.stdout.write(f"Warning: Missing variables: {missing_vars}")
        
        # Calculate wind speed
        if '10m_u_component_of_wind' in data['variables'] and '10m_v_component_of_wind' in data['variables']:
            speed_10m, direction_10m = self.calculate_wind_speed_direction(
                data['variables']['10m_u_component_of_wind'],
                data['variables']['10m_v_component_of_wind']
            )
        
        # Convert units
        temperature = self.convert_temperature(data['variables']['2m_temperature'])
        pressure = self.convert_pressure(data['variables']['surface_pressure'])
        ghi = data['variables']['surface_solar_radiation_downwards']  # Already in W/m²
        
        # Create files
        if self.specific_coords:
            for lat, lon in self.specific_coords:
                self.create_solar_file_for_point(
                    lat, lon, data['times'], data['lats'], data['lons'],
                    ghi, temperature, pressure, speed_10m, direction_10m
                )
        else:
            self.stdout.write("Processing all grid points (this may take a while)...")
            for i, lat in enumerate(data['lats']):
                for j, lon in enumerate(data['lons']):
                    if self.boundaries['south'] <= lat <= self.boundaries['north'] and \
                       self.boundaries['west'] <= lon <= self.boundaries['east']:
                        self.create_solar_file_for_point(
                            lat, lon, data['times'], data['lats'], data['lons'],
                            ghi, temperature, pressure, speed_10m, direction_10m,
                            grid_indices=(i, j)
                        )

    def create_solar_file_for_point(self, lat, lon, times, lats, lons, ghi, temperature, 
                                   pressure, speed_10m, direction_10m, grid_indices=None):
        """Create solar file for a specific point"""
        
        if self.format == 'csv':
            filename = f'solar_weather_{lat:.4f}_{lon:.4f}_{self.year}.csv'
        else:
            filename = f'solar_weather_{lat:.4f}_{lon:.4f}_{self.year}.smw'
        
        filepath = os.path.join(self.output_dir, filename)
        
        with open(filepath, 'w') as f:
            if self.format == 'csv':
                # SAM CSV format
                f.write('Location,City,Region,Country,Latitude,Longitude,Time Zone,Elevation,Source\n')
                f.write(f'id,<city>,<state>,<country>,{lat:.4f},{lon:.4f},{self.timezone},0,ERA5\n')
                f.write('Year,Month,Day,Hour,GHI,DNI,DHI,Tdry,Pres,Wspd,Wdir\n')
                
                month = 1
                day = 1
                hour = 0
                
                for time_obj in times:
                    # Get values for this time step
                    if grid_indices:
                        i, j = grid_indices
                        if isinstance(ghi, dict):
                            ghi_val = ghi[time_obj][i, j]
                            temp_val = temperature[time_obj][i, j]
                            press_val = pressure[time_obj][i, j]
                            speed_val = speed_10m[time_obj][i, j]
                            dir_val = direction_10m[time_obj][i, j]
                        else:
                            time_idx = times.index(time_obj)
                            ghi_val = ghi[time_idx, i, j]
                            temp_val = temperature[time_idx, i, j]
                            press_val = pressure[time_idx, i, j]
                            speed_val = speed_10m[time_idx, i, j]
                            dir_val = direction_10m[time_idx, i, j]
                    else:
                        # Interpolate
                        ghi_interp = self.interpolate_to_point(ghi, lat, lon, lats, lons)
                        temp_interp = self.interpolate_to_point(temperature, lat, lon, lats, lons)
                        press_interp = self.interpolate_to_point(pressure, lat, lon, lats, lons)
                        speed_interp = self.interpolate_to_point(speed_10m, lat, lon, lats, lons)
                        dir_interp = self.interpolate_to_point(direction_10m, lat, lon, lats, lons)
                        
                        if isinstance(ghi_interp, dict):
                            ghi_val = ghi_interp[time_obj]
                            temp_val = temp_interp[time_obj]
                            press_val = press_interp[time_obj]
                            speed_val = speed_interp[time_obj]
                            dir_val = dir_interp[time_obj]
                        else:
                            time_idx = times.index(time_obj)
                            ghi_val = ghi_interp[time_idx]
                            temp_val = temp_interp[time_idx]
                            press_val = press_interp[time_idx]
                            speed_val = speed_interp[time_idx]
                            dir_val = dir_interp[time_idx]
                    
                    # Calculate DNI and DHI
                    dni_val, dhi_val = self.calculate_dni_dhi(ghi_val, hour, lat, lon, press_val)
                    
                    # Write data
                    f.write(f'{self.year},{month:02d},{day:02d},{hour:02d},'
                           f'{ghi_val:.1f},{dni_val:.1f},{dhi_val:.1f},'
                           f'{temp_val:.1f},{press_val:.0f},{speed_val:.1f},{dir_val:.0f}\n')
                    
                    # Increment time
                    hour += 1
                    if hour >= 24:
                        hour = 0
                        day += 1
                        # Handle month rollover (simplified)
                        days_in_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
                        if self.year % 4 == 0 and month == 2:  # Leap year
                            days_in_month[1] = 29
                        
                        if day > days_in_month[month - 1]:
                            day = 1
                            month += 1
                            if month > 12:
                                break  # End of year
            
            else:  # SMW format
                # SAM weather file format
                f.write(f'id,<city>,<state>,{self.timezone},{lat:.4f},{lon:.4f},0,3600.0,{self.year},0:30:00\n')
                
                for time_obj in times:
                    # Get values for this time step (similar to above)
                    if grid_indices:
                        i, j = grid_indices
                        if isinstance(ghi, dict):
                            ghi_val = ghi[time_obj][i, j]
                            temp_val = temperature[time_obj][i, j]
                            press_val = pressure[time_obj][i, j]
                            speed_val = speed_10m[time_obj][i, j]
                            dir_val = direction_10m[time_obj][i, j]
                        else:
                            time_idx = times.index(time_obj)
                            ghi_val = ghi[time_idx, i, j]
                            temp_val = temperature[time_idx, i, j]
                            press_val = pressure[time_idx, i, j]
                            speed_val = speed_10m[time_idx, i, j]
                            dir_val = direction_10m[time_idx, i, j]
                    else:
                        # Interpolate (same as above)
                        ghi_interp = self.interpolate_to_point(ghi, lat, lon, lats, lons)
                        temp_interp = self.interpolate_to_point(temperature, lat, lon, lats, lons)
                        press_interp = self.interpolate_to_point(pressure, lat, lon, lats, lons)
                        speed_interp = self.interpolate_to_point(speed_10m, lat, lon, lats, lons)
                        dir_interp = self.interpolate_to_point(direction_10m, lat, lon, lats, lons)
                        
                        if isinstance(ghi_interp, dict):
                            ghi_val = ghi_interp[time_obj]
                            temp_val = temp_interp[time_obj]
                            press_val = press_interp[time_obj]
                            speed_val = speed_interp[time_obj]
                            dir_val = dir_interp[time_obj]
                        else:
                            time_idx = times.index(time_obj)
                            ghi_val = ghi_interp[time_idx]
                            temp_val = temp_interp[time_idx]
                            press_val = press_interp[time_idx]
                            speed_val = speed_interp[time_idx]
                            dir_val = dir_interp[time_idx]
                    
                    # Calculate hour of year for DNI/DHI calculation
                    hour_of_year = times.index(time_obj)
                    dni_val, dhi_val = self.calculate_dni_dhi(ghi_val, hour_of_year % 24, lat, lon, press_val)
                    
                    # SMW format: temp, dewpoint, humidity, pressure, wind_speed, wind_dir, pressure, ghi, dni, dhi, albedo, snow
                    f.write(f'{temp_val:.1f},-999,-999,-999,{speed_val:.1f},{dir_val:.0f},{press_val:.1f},'
                           f'{ghi_val:.0f},{dni_val:.0f},{dhi_val:.0f},-999,-999,\n')
        
        self.stdout.write(f'Created: {filename}')

    def validate_era5_data(self, data):
        """Validate the ERA5 data structure"""
        required_keys = ['lats', 'lons', 'times', 'variables']
        for key in required_keys:
            if key not in data:
                raise CommandError(f'Missing required data key: {key}')
        
        if not data['times']:
            raise CommandError('No time data found in file')
        
        if not data['variables']:
            raise CommandError('No variables found in file')
        
        # Check if we have data within our boundaries
        lat_in_bounds = any(self.boundaries['south'] <= lat <= self.boundaries['north'] 
                           for lat in data['lats'])
        lon_in_bounds = any(self.boundaries['west'] <= lon <= self.boundaries['east'] 
                           for lon in data['lons'])
        
        if not (lat_in_bounds and lon_in_bounds):
            self.stdout.write(
                self.style.WARNING(
                    'Warning: ERA5 data may not cover South West WA region completely.\n'
                    f'Data bounds: {data["lats"].min():.2f}°S to {data["lats"].max():.2f}°S, '
                    f'{data["lons"].min():.2f}°E to {data["lons"].max():.2f}°E\n'
                    f'Expected bounds: {self.boundaries["south"]}°S to {self.boundaries["north"]}°S, '
                    f'{self.boundaries["west"]}°E to {self.boundaries["east"]}°E'
                )
            )
        
        self.stdout.write(f'Validation complete: {len(data["variables"])} variables, {len(data["times"])} time steps')


# Utility functions for wind extrapolation (similar to original code)
def extrapolate_wind_profile(input_file, hub_height, law='logarithmic', replace=False):
    """
    Extrapolate wind data to different hub height
    This function can be used independently or called from the management command
    """
    if not os.path.exists(input_file):
        return False
    
    # Read existing file
    with open(input_file, 'r') as f:
        lines = f.readlines()
    
    # Check if it's a wind file
    if not input_file.endswith('.srw'):
        return False
    
    # Process the file to add hub height data
    new_lines = []
    header_processed = False
    
    for line in lines:
        if not header_processed and line.startswith('Temperature'):
            # Update header to include hub height
            if hub_height not in line:
                line = line.rstrip() + f',Direction,Speed\n'
                new_lines.append(line)
                # Add units line
                next_line = next(lines).__iter__()
                if 'C,atm,degrees' in next_line:
                    next_line = next_line.rstrip() + f',degrees,m/s\n'
                new_lines.append(next_line)
                # Add height line
                height_line = next(lines).__iter__()
                if '2,0,10,10' in height_line:
                    height_line = height_line.rstrip() + f',{hub_height},{hub_height}\n'
                new_lines.append(height_line)
                header_processed = True
                continue
        
        if header_processed and ',' in line and not line.startswith('id') and not line.startswith('Wind'):
            # Process data line
            parts = line.strip().split(',')
            if len(parts) >= 6:
                try:
                    speed_100m = float(parts[5])  # 100m wind speed
                    direction_100m = float(parts[4])  # 100m wind direction
                    
                    # Extrapolate to hub height
                    if law == 'hellman' or law == 'h':
                        # Hellman exponential law
                        alpha = 0.143
                        hub_speed = speed_100m * (hub_height / 100.0) ** alpha
                    else:
                        # Logarithmic law
                        z0 = 0.1  # Roughness length
                        hub_speed = speed_100m * np.log(hub_height / z0) / np.log(100.0 / z0)
                    
                    # Add extrapolated data
                    line = line.rstrip() + f',{direction_100m:.0f},{hub_speed:.4f}\n'
                except (ValueError, IndexError):
                    pass
        
        new_lines.append(line)
    
    # Write back to file
    output_file = input_file if replace else input_file.replace('.srw', f'_hub{hub_height}.srw')
    with open(output_file, 'w') as f:
        f.writelines(new_lines)
    
    return True