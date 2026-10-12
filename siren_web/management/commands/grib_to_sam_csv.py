#!/usr/bin/env python3
"""
Django Management Command for converting ERA5 GRIB data to SAM CSV format

Handles the multi-dataset structure of ERA5 GRIB files:
- Instantaneous variables (temperature, wind, pressure)
- Accumulated radiation variables (needs special processing)

Usage:
python manage.py grib_to_sam_csv --input-dir=weather_data --output-dir=weather_output --resource-type=solar --year=2025

Every CSV row is one UTC hour, labelled by the start of that hour.
"""

import os
import numpy as np
import math
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand, CommandError

from siren_web.utilities.solar_geometry import hour_midpoints_utc, split_ghi_erbs


class Command(BaseCommand):
    help = 'Convert ERA5 GRIB data to SAM CSV format for solar and wind resources'

    def add_arguments(self, parser):
        parser.add_argument(
            '--input-dir',
            type=str,
            required=True,
            help='Directory containing ERA5 GRIB files'
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
            choices=['solar', 'wind', 'both'],
            help='Type of resource file to create'
        )

        parser.add_argument(
            '--coordinates',
            type=str,
            help='Specific lat,lon to process (e.g., "-31.95,115.86")'
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
            default=0,
            help='Deprecated and ignored: rows are always UTC and the files say time zone 0'
        )

    def handle(self, *args, **options):
        try:
            import cfgrib
            import xarray as xr
        except ImportError:
            raise CommandError(
                'cfgrib and xarray are required.\n'
                'Install with: pip install xarray cfgrib eccodes'
            )

        self.cfgrib = cfgrib
        self.xr = xr
        self.options = options
        self.year = options['year']
        self.timezone = options['timezone']
        self.resource_type = options['resource_type']
        self.input_dir = options['input_dir']

        # Create output directory
        output_dir = options['output_dir']
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            self.stdout.write(f'Created output directory: {output_dir}')

        # Find GRIB files
        self.grib_files = self.find_grib_files()

        if not self.grib_files:
            raise CommandError(
                f'No GRIB files found for {self.year} in {self.input_dir}'
            )

        self.stdout.write(f'Found {len(self.grib_files)} GRIB files')

        # Load all data
        self.load_era5_data()

        # Process locations
        if options['coordinates']:
            lat, lon = map(float, options['coordinates'].split(','))
            self.process_location(lat, lon)
        else:
            self.process_all_locations()

    def find_grib_files(self):
        """Find all monthly GRIB files"""
        import glob
        pattern = os.path.join(self.input_dir, f'era5_data_{self.year}_*.grib')
        return sorted(glob.glob(pattern))

    def load_era5_data(self):
        """Load ERA5 GRIB data handling multiple dataset groups"""
        self.stdout.write('Loading ERA5 GRIB data...')

        # Storage for merged data
        all_instant_data = []
        all_accum_data = []

        for grib_file in self.grib_files:
            self.stdout.write(f'  Processing {os.path.basename(grib_file)}...')

            # Open all dataset groups in this file
            datasets = self.cfgrib.open_datasets(grib_file)

            for ds in datasets:
                vars_in_ds = list(ds.data_vars)

                # Check if this is instantaneous or accumulated data
                if 'ssrd' in vars_in_ds:
                    # Accumulated radiation data - needs special handling
                    all_accum_data.append(ds)
                else:
                    # Instantaneous data
                    all_instant_data.append(ds)

        # Merge instantaneous datasets along time
        self.stdout.write('Merging instantaneous data...')
        self.instant_ds = self.xr.concat(all_instant_data, dim='time')
        self.instant_ds = self.instant_ds.sortby('time')

        # Get coordinate grids
        self.lats = self.instant_ds.latitude.values
        self.lons = self.instant_ds.longitude.values
        self.times = self.instant_ds.time.values

        self.stdout.write(
            f'Instantaneous data: {len(self.times)} hours, '
            f'{len(self.lats)}x{len(self.lons)} grid'
        )
        self.stdout.write(f'Variables: {list(self.instant_ds.data_vars)}')

        # Process accumulated radiation data
        self.stdout.write('Processing accumulated radiation data...')
        self.process_accumulated_radiation(all_accum_data)

    def process_accumulated_radiation(self, accum_datasets):
        """
        Place ERA5 hourly radiation onto the hourly rows.

        In ERA5 (as delivered by the current CDS) every forecast step of `ssrd`/`ssr`
        is already the accumulation over the ONE hour ending at that step's valid time
        -- it is not cumulative since the forecast start, so it must not be differenced.
        (Differencing it produced files with roughly a quarter of the real annual
        irradiance, all in the wrong hours.)

        Rows are labelled by the START of the hour they cover, so the value valid at
        time V goes in the row for V - 1 h. The final row of the year needs a value
        valid at 00:00 on 1 January of the next year, which is in the next year's
        files; when that is missing it is filled from the same hour a day earlier.
        """
        combined = self.xr.concat(accum_datasets, dim='time')
        combined = combined.sortby('time')

        n_times = len(self.times)
        n_lats = len(self.lats)
        n_lons = len(self.lons)

        self.ssrd_hourly = np.full((n_times, n_lats, n_lons), np.nan)
        self.ssr_hourly = np.full((n_times, n_lats, n_lons), np.nan)

        row_of_hour = {t: i for i, t in enumerate(self.times.astype('datetime64[h]'))}
        valid_times = combined.valid_time.values.astype('datetime64[h]')  # (time, step)
        ssrd = combined.ssrd.values  # (time, step, lat, lon)
        ssr = combined.ssr.values

        for t_idx in range(valid_times.shape[0]):
            for s_idx in range(valid_times.shape[1]):
                row = row_of_hour.get(valid_times[t_idx, s_idx] - np.timedelta64(1, 'h'))
                if row is None:
                    continue
                value = ssrd[t_idx, s_idx]
                if np.all(np.isnan(value)):
                    continue  # steps before the first forecast in the files
                self.ssrd_hourly[row] = value
                self.ssr_hourly[row] = ssr[t_idx, s_idx]

        for name, arr in (('ssrd', self.ssrd_hourly), ('ssr', self.ssr_hourly)):
            missing = np.flatnonzero(np.all(np.isnan(arr), axis=(1, 2)))
            for row in missing:
                if row >= 24:
                    arr[row] = arr[row - 24]
            still_missing = np.all(np.isnan(arr), axis=(1, 2)).sum()
            if len(missing):
                self.stdout.write(
                    f'  {name}: {len(missing)} hour(s) had no ERA5 value; filled from the day '
                    f'before ({still_missing} left as zero)'
                )
            np.nan_to_num(arr, copy=False)

        self.stdout.write(f'Radiation data processed: {n_times} hourly values')

    def process_all_locations(self):
        """Process all grid points"""
        total = len(self.lats) * len(self.lons)
        self.stdout.write(f'Processing {total} locations...')

        count = 0
        for lat in self.lats:
            for lon in self.lons:
                self.process_location(float(lat), float(lon))
                count += 1
                if count % 50 == 0:
                    self.stdout.write(f'  Processed {count}/{total}')

        self.stdout.write(self.style.SUCCESS(f'Completed {count} locations'))

    def process_location(self, lat, lon):
        """Process a single location"""
        # Find nearest grid point indices
        lat_idx = np.abs(self.lats - lat).argmin()
        lon_idx = np.abs(self.lons - lon).argmin()
        actual_lat = float(self.lats[lat_idx])
        actual_lon = float(self.lons[lon_idx])

        # Extract time series data for this location
        location_data = self.extract_location_data(lat_idx, lon_idx)

        # Generate SAM files
        if self.resource_type in ['solar', 'both']:
            self.write_solar_csv(actual_lat, actual_lon, location_data)

        if self.resource_type in ['wind', 'both']:
            self.write_wind_csv(actual_lat, actual_lon, location_data)

    def extract_location_data(self, lat_idx, lon_idx):
        """Extract all time series data for a grid point"""
        data = {'times': self.times}

        # Extract instantaneous variables
        for var in ['t2m', 'd2m', 'sp', 'u10', 'v10', 'u100', 'v100', 'tcc']:
            if var in self.instant_ds:
                data[var] = self.instant_ds[var].values[:, lat_idx, lon_idx]
            else:
                data[var] = np.zeros(len(self.times))

        # Extract hourly radiation
        data['ssrd'] = self.ssrd_hourly[:, lat_idx, lon_idx]
        data['ssr'] = self.ssr_hourly[:, lat_idx, lon_idx]

        return data

    def write_solar_csv(self, lat, lon, data):
        """Write SAM solar CSV file"""
        output_file = os.path.join(
            self.options['output_dir'],
            f'solar_{lat:.4f}_{lon:.4f}_{self.year}.csv'
        )

        # GHI: J/m² accumulated over the hour -> mean W/m² over the hour
        ghi_all = np.clip(np.asarray(data['ssrd'], dtype=float) / 3600.0, 0.0, None)
        # Each row is labelled by the start of its hour; the sun is taken at mid-hour
        midpoints = hour_midpoints_utc(data['times'])
        dni_all, dhi_all = split_ghi_erbs(ghi_all, midpoints, lat, lon)

        with open(output_file, 'w') as f:
            # SAM header format. Rows are UTC, so the time zone written is 0.
            f.write('Latitude,Longitude,Time Zone,Elevation\n')
            f.write(f'{lat:.4f},{lon:.4f},0,0\n')
            f.write('Year,Month,Day,Hour,Minute,GHI,DNI,DHI,Tdry,Tdew,RH,Pres,Wspd,Wdir\n')

            # Data rows - one per hour
            for i, time_val in enumerate(data['times']):
                # Convert numpy datetime64 to Python datetime
                dt = self.np_datetime_to_python(time_val)

                ghi = float(ghi_all[i])
                dni = float(dni_all[i])
                dhi = float(dhi_all[i])

                # Temperature: Kelvin to Celsius
                tdry = data['t2m'][i] - 273.15
                tdew = data['d2m'][i] - 273.15

                # Relative humidity
                rh = self.calculate_rh(tdry, tdew)

                # Pressure: Pa to millibar
                pres = data['sp'][i] / 100.0

                # Wind speed and direction
                wspd, wdir = self.calc_wind(data['u10'][i], data['v10'][i])

                f.write(
                    f'{dt.year},{dt.month},{dt.day},{dt.hour},{dt.minute},'
                    f'{ghi:.1f},{dni:.1f},{dhi:.1f},'
                    f'{tdry:.1f},{tdew:.1f},{rh:.0f},'
                    f'{pres:.1f},{wspd:.1f},{wdir:.0f}\n'
                )

    def write_wind_csv(self, lat, lon, data):
        """Write SAM wind CSV file"""
        output_file = os.path.join(
            self.options['output_dir'],
            f'wind_{lat:.4f}_{lon:.4f}_{self.year}.csv'
        )

        site_name = f'Grid_{lat:.2f}_{lon:.2f}'

        with open(output_file, 'w') as f:
            # SAM wind header
            f.write(
                f'SiteID,{site_name},Site Timezone,8,'
                f'Data Timezone,0,Longitude,{lon:.4f},'
                f'Latitude,{lat:.4f},Elevation,0\n'
            )
            f.write('Temperature,Pressure,Speed,Direction,'
                   'Speed,Direction\n')

            # Data rows
            for i in range(len(data['times'])):
                temp = data['t2m'][i] - 273.15
                pres = data['sp'][i] / 101325.0  # Pa to atm

                wspd10, wdir10 = self.calc_wind(data['u10'][i], data['v10'][i])
                wspd100, wdir100 = self.calc_wind(data['u100'][i], data['v100'][i])

                f.write(
                    f'{temp:.2f},{pres:.5f},'
                    f'{wspd10:.2f},{wdir10:.0f},'
                    f'{wspd100:.2f},{wdir100:.0f}\n'
                )

    def np_datetime_to_python(self, np_dt):
        """Convert numpy datetime64 to Python datetime"""
        ts = (np_dt - np.datetime64('1970-01-01T00:00:00')) / np.timedelta64(1, 's')
        return datetime.utcfromtimestamp(ts)

    def calculate_rh(self, temp_c, dewpoint_c):
        """Calculate relative humidity using Magnus formula"""
        try:
            a, b = 17.625, 243.04
            rh = 100.0 * math.exp(
                (a * dewpoint_c) / (b + dewpoint_c) - (a * temp_c) / (b + temp_c)
            )
            return max(0.0, min(100.0, rh))
        except:
            return 50.0

    def calc_wind(self, u, v):
        """Calculate wind speed and direction from U/V components"""
        speed = math.sqrt(u**2 + v**2)
        direction = (270.0 - math.degrees(math.atan2(v, u))) % 360.0
        return speed, direction
