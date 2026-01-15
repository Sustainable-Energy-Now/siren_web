#!/usr/bin/env python3
"""
Django Management Command for retrieving ERA5 weather data for South West WA
Based on getera5.py from SIREN project

Usage:
python manage.py retrieve_era5_data [options]
"""

import os
import cdsapi
from datetime import datetime
from netCDF4 import Dataset
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings


class Command(BaseCommand):
    help = 'Retrieve ERA5 solar and wind weather data for South West Western Australia'

    def add_arguments(self, parser):
        parser.add_argument(
            '--start-year',
            type=int,
            default=datetime.now().year - 1,
            help='Start year for data retrieval (default: last year)'
        )
        
        parser.add_argument(
            '--end-year',
            type=int,
            default=datetime.now().year - 1,
            help='End year for data retrieval (default: last year)'
        )
        
        parser.add_argument(
            '--start-month',
            type=int,
            default=1,
            help='Start month (1-12, default: 1)'
        )
        
        parser.add_argument(
            '--end-month',
            type=int,
            default=12,
            help='End month (1-12, default: 12)'
        )
        
        parser.add_argument(
            '--output-dir',
            type=str,
            default=os.path.join(settings.BASE_DIR, 'weather_data'),
            help='Directory to save ERA5 files'
        )
        
        parser.add_argument(
            '--grid-resolution',
            type=float,
            default=0.25,
            help='Grid resolution in degrees (default: 0.25)'
        )
        
        parser.add_argument(
            '--check-existing',
            action='store_true',
            help='Check existing files and show coverage'
        )
        
        parser.add_argument(
            '--config-file',
            type=str,
            help='Path to configuration file'
        )
        
        parser.add_argument(
            '--validate-credentials',
            action='store_true',
            help='Only validate CDS API credentials without downloading data'
        )
        parser.add_argument(
            '--test-era-request',
            action='store_true',
            help='Test a small data era request to verify API connectivity'
        )
        parser.add_argument(
            '--test-request',
            action='store_true',
            help='Test a small data request to verify API connectivity'
        )
        
        parser.add_argument(
            '--existing',
            action='store_true',
            help='Extract an existing manually created dataset'
        )
    def handle(self, *args, **options):
        # South West Western Australia boundaries
        # Approximate boundaries covering Perth, Bunbury, Albany region
        self.boundaries = {
            'north': -28.0,   # Northern boundary (around Geraldton)
            'south': -35.0,   # Southern boundary (around Albany)
            'west': 113.0,    # Western boundary (Extended for offshore wind zones)
            'east': 120.0     # Eastern boundary (inland)
        }
        
        self.options = options
        self.setup_output_directory()
        
        if options['check_existing']:
            self.check_existing_files()
            return
            
        if options['validate_credentials']:
            self.validate_cdsapi_credentials()
            self.stdout.write(self.style.SUCCESS('CDS API credentials are valid!'))
            return
            
        if options['test_era_request']:
            self.test_era_request()
            return
        
        if options['test_request']:
            self.test_small_request()
            return
        
        # Check data availability before attempting download
        start_year = options['start_year']
        end_year = options['end_year']
        current_year = datetime.now().year
        
        # ERA5 has a 2-3 month delay, so check if requested years are available
        if end_year >= current_year:
            self.stdout.write(
                self.style.WARNING(
                    f'Warning: ERA5 data has a 2-3 month delay from real-time. '
                    f'Data for {current_year} may not be fully available yet. '
                    f'Consider using {current_year - 1} instead.'
                )
            )
        
        self.validate_cdsapi_credentials()
        if options['existing']:
            self.retrieve_existing_data()
        else:
            self.retrieve_data()

    def setup_output_directory(self):
        """Create output directory if it doesn't exist"""
        self.output_dir = self.options['output_dir']
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
            self.stdout.write(
                self.style.SUCCESS(f'Created output directory: {self.output_dir}')
            )

    def validate_cdsapi_credentials(self):
        """Check if CDS API credentials are configured"""
        home_dir = os.path.expanduser('~')
        cdsapirc_path = os.path.join(home_dir, '.cdsapirc')
        
        if not os.path.exists(cdsapirc_path):
            raise CommandError(
                f'CDS API credentials file not found at {cdsapirc_path}\n'
                'Please create this file with your CDS API credentials:\n'
                'url: https://cds.climate.copernicus.eu/api\n'
                'key: <your-uid>:<your-api-key>\n'
                'Get your credentials from: https://cds.climate.copernicus.eu/api-how-to'
            )
        
        # Validate the format of the credentials
        try:
            with open(cdsapirc_path, 'r') as f:
                content = f.read()
                
            lines = content.strip().split('\n')
            url_found = False
            key_found = False
            key_format_valid = False
            
            for line in lines:
                line = line.strip()
                if line.startswith('url:'):
                    url_found = True
                elif line.startswith('key:'):
                    key_found = True
                    # Extract the key part and validate format
                    key_value = line.split('key:', 1)[1].strip()
                    key_format_valid = True
            
            if not url_found:
                raise CommandError(
                    f'Invalid .cdsapirc file: missing "url" line.\n'
                    f'Your file should contain:\n'
                    f'url: https://cds.climate.copernicus.eu/api\n'
                    f'key: <your-uid>:<your-api-key>'
                )
            
            if not key_found:
                raise CommandError(
                    f'Invalid .cdsapirc file: missing "key" line.\n'
                    f'Your file should contain:\n'
                    f'url: https://cds.climate.copernicus.eu/api\n'
                    f'key: <your-uid>:<your-api-key>'
                )
            
            if not key_format_valid:
                raise CommandError(
                    f'Invalid API key format in .cdsapirc file.\n'
                    f'The key should be in format: <APIKEY>\n'
                    f'Where:\n'
                    f'  - APIKEY is your long API key string\n'
                    f'Examples:\n'
                    f'  key: abcd1234-ef56-7890-abcd-1234567890ab\n'
                    f'To get your credentials:\n'
                    f'1. Go to https://cds.climate.copernicus.eu/user/login\n'
                    f'2. Log in to your account\n'
                    f'3. Go to https://cds.climate.copernicus.eu/api-how-to\n'
                    f'4. Copy the EXACT text shown on that page\n'
                    f'5. Update your {cdsapirc_path} file'
                )
                
        except FileNotFoundError:
            raise CommandError(f'Could not read .cdsapirc file at {cdsapirc_path}')
        except Exception as e:
            raise CommandError(f'Error validating .cdsapirc file: {str(e)}')

    def get_era5_variables(self):
        """Return ERA5 variables for comprehensive solar and wind energy analysis"""
        return {
            'solar_variables': [
                'surface_solar_radiation_downwards',  # GHI - Global Horizontal Irradiance
                'surface_net_solar_radiation',        # Net solar radiation
                'total_cloud_cover',                   # Cloud cover (affects radiation)
                '2m_temperature',                      # Air temperature (affects PV efficiency)
                '2m_dewpoint_temperature'              # Dewpoint for RH calculation
            ],
            'wind_variables': [
                '10m_u_component_of_wind',            # 10m wind U-component
                '10m_v_component_of_wind',            # 10m wind V-component
                '100m_u_component_of_wind',           # 100m wind U-component (closer to hub height)
                '100m_v_component_of_wind',           # 100m wind V-component
                'surface_pressure'                    # Surface pressure (for air density)
            ],
            'additional_variables': [
                'surface_solar_radiation_downward_clear_sky',  # Clear sky radiation for cloud index
            ]
        }

    def create_era5_request(self, year, month=None, variables=None):
        """Create ERA5 API request dictionary"""
        if variables is None:
            var_dict = self.get_era5_variables()
            # Combine all variable types for comprehensive energy analysis
            variables = (var_dict['solar_variables'] +
                        var_dict['wind_variables'] +
                        var_dict['additional_variables'])

        # Get actual number of days in the month to avoid requesting invalid dates
        import calendar
        if month:
            num_days = calendar.monthrange(year, month)[1]
            days = [f'{d:02d}' for d in range(1, num_days + 1)]
        else:
            # For full year, include all possible days (API handles invalid dates like Feb 30)
            days = [f'{d:02d}' for d in range(1, 32)]

        # Request structure matching working CDS Beta API format
        request = {
            'product_type': 'reanalysis',  # String, not list (CDS Beta format)
            'variable': variables,
            'year': str(year),  # String, not list
            'month': f'{month:02d}' if month else [f'{m:02d}' for m in range(1, 13)],
            'day': days,
            'time': [f'{h:02d}:00' for h in range(24)],
            'data_format': 'grib',  # GRIB format (default, proven to work)
            'download_format': 'unarchived',
            'area': [
                self.boundaries['north'],
                self.boundaries['west'],
                self.boundaries['south'],
                self.boundaries['east']
            ]
        }

        return request

    def generate_filename(self, year, month=None):
        """Generate filename for ERA5 data"""
        if month:
            return f'era5_data_{year}_{month:02d}.grib'
        else:
            return f'era5_data_{year}.grib'

    def retrieve_data(self):
        """Main data retrieval function"""
        start_year = self.options['start_year']
        end_year = self.options['end_year']
        start_month = self.options['start_month']
        end_month = self.options['end_month']
        
        self.stdout.write(
            f'Retrieving ERA5 data for South West WA:\n'
            f'  Area: {self.boundaries["north"]}°N to {self.boundaries["south"]}°N, '
            f'{self.boundaries["west"]}°E to {self.boundaries["east"]}°E\n'
            f'  Period: {start_year}/{start_month:02d} to {end_year}/{end_month:02d}\n'
            f'  Grid: {self.options["grid_resolution"]}° x {self.options["grid_resolution"]}°'
        )
        
        try:
            c = cdsapi.Client()
            
            for year in range(start_year, end_year + 1):
                # Determine month range for this year
                year_start_month = start_month if year == start_year else 1
                year_end_month = end_month if year == end_year else 12
                
                if year_start_month == 1 and year_end_month == 12:
                    # Download full year at once
                    self.retrieve_year_data(c, year)
                else:
                    # Download month by month
                    for month in range(year_start_month, year_end_month + 1):
                        self.retrieve_month_data(c, year, month)
                        
        except Exception as e:
            raise CommandError(f'Error retrieving ERA5 data: {str(e)}')

    def retrieve_existing_data(self):
        """Main data retrieval function"""
        start_year = self.options['start_year']
        end_year = self.options['end_year']
        start_month = self.options['start_month']
        end_month = self.options['end_month']
        
        self.stdout.write(
            f'Retrieving ERA5 data for South West WA:\n'
            f'  Area: {self.boundaries["north"]}°N to {self.boundaries["south"]}°N, '
            f'{self.boundaries["west"]}°E to {self.boundaries["east"]}°E\n'
            f'  Period: {start_year}/{start_month:02d} to {end_year}/{end_month:02d}\n'
            f'  Grid: {self.options["grid_resolution"]}° x {self.options["grid_resolution"]}°'
        )
        
        try:
            dataset = "reanalysis-era5-single-levels"
            request = {
                "product_type": ["reanalysis"],
                "variable": [
                    "10m_u_component_of_wind",
                    "10m_v_component_of_wind",
                    "100m_u_component_of_wind",
                    "100m_v_component_of_wind",
                    "surface_solar_radiation_downwards"
                ],
                "year": ["2025"],
                "month": [
                    "01", "02", "03",
                    "04", "05", "06",
                    "07", "08", "09",
                    "10", "11", "12"
                ],
                "day": [
                    "01", "02", "03",
                    "04", "05", "06",
                    "07", "08", "09",
                    "10", "11", "12",
                    "13", "14", "15",
                    "16", "17", "18",
                    "19", "20", "21",
                    "22", "23", "24",
                    "25", "26", "27",
                    "28", "29", "30",
                    "31"
                ],
                "time": [
                    "00:00", "01:00", "02:00",
                    "03:00", "04:00", "05:00",
                    "06:00", "07:00", "08:00",
                    "09:00", "10:00", "11:00",
                    "12:00", "13:00", "14:00",
                    "15:00", "16:00", "17:00",
                    "18:00", "19:00", "20:00",
                    "21:00", "22:00", "23:00"
                ],
                "data_format": "grib",
                "download_format": "unarchived",
                "area": [-28, 114, -35, 120]
            }

            client = cdsapi.Client()
            client.retrieve(dataset, request).download()
   
        except Exception as e:
            raise CommandError(f'Error retrieving ERA5 data: {str(e)}')

    def retrieve_year_data(self, client, year):
        """Retrieve full year of data"""
        filename = self.generate_filename(year)
        filepath = os.path.join(self.output_dir, filename)
        
        if os.path.exists(filepath):
            self.stdout.write(f'File {filename} already exists, skipping...')
            return
            
        self.stdout.write(f'Downloading {filename}...')
        
        request = self.create_era5_request(year)
        
        # Save request details
        request_file = filepath.replace('.nc', '_request.txt')
        with open(request_file, 'w') as f:
            for key, value in request.items():
                f.write(f'{key}: {value}\n')
        
        try:
            client.retrieve('reanalysis-era5-single-levels', request, filepath)
            self.stdout.write(
                self.style.SUCCESS(f'Successfully downloaded {filename}')
            )
            self.validate_downloaded_file(filepath)
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Failed to download {filename}: {str(e)}')
            )
            # Try to provide helpful error messages
            error_msg = str(e).lower()
            if 'endpoint not found' in error_msg or 'api endpoint' in error_msg:
                self.stdout.write(
                    self.style.WARNING(
                        f'\n'
                        f'API Endpoint Error - This usually means:\n'
                        f'  1. You need to accept the dataset Terms of Use first:\n'
                        f'     - Visit: https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels\n'
                        f'     - Click "Download data" tab\n'
                        f'     - Accept the Terms of Use if prompted\n'
                        f'  2. Or the CDS API may be undergoing maintenance\n'
                        f'  3. Check CDS status: https://cds.climate.copernicus.eu/live/status\n'
                    )
                )
            elif 'not found' in error_msg:
                self.stdout.write(
                    self.style.WARNING(
                        f'Data not found error - possible causes:\n'
                        f'  - ERA5 data for {year} may not be available yet (2-3 month delay)\n'
                        f'  - Some variables may not be available for the requested period\n'
                        f'  - Temporary CDS system issues\n'
                        f'Try using --test-request to test with a smaller request'
                    )
                )

    def retrieve_month_data(self, client, year, month):
        """Retrieve single month of data"""
        filename = self.generate_filename(year, month)
        filepath = os.path.join(self.output_dir, filename)
        
        if os.path.exists(filepath):
            self.stdout.write(f'File {filename} already exists, skipping...')
            return
            
        self.stdout.write(f'Downloading {filename}...')
        
        request = self.create_era5_request(year, month)
        
        # Save request details
        request_file = filepath.replace('.nc', '_request.txt')
        with open(request_file, 'w') as f:
            for key, value in request.items():
                f.write(f'{key}: {value}\n')
        
        try:
            client.retrieve('reanalysis-era5-single-levels', request, filepath)
            self.stdout.write(
                self.style.SUCCESS(f'Successfully downloaded {filename}')
            )
            self.validate_downloaded_file(filepath)
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Failed to download {filename}: {str(e)}')
            )

    def validate_downloaded_file(self, filepath):
        """Validate downloaded GRIB or NetCDF file"""
        try:
            file_size = os.path.getsize(filepath)
            self.stdout.write(f'  File validation: {os.path.basename(filepath)}')
            self.stdout.write(f'    File size: {file_size / (1024*1024):.1f} MB')

            # For GRIB files, we can do basic validation
            if filepath.endswith('.grib'):
                try:
                    import pygrib
                    grbs = pygrib.open(filepath)
                    num_messages = grbs.messages
                    self.stdout.write(f'    GRIB messages: {num_messages}')

                    # Read first message to check coordinates
                    if num_messages > 0:
                        grb = grbs.message(1)
                        lats, lons = grb.latlons()
                        self.stdout.write(f'    Latitude range: {lats.min():.3f} to {lats.max():.3f}')
                        self.stdout.write(f'    Longitude range: {lons.min():.3f} to {lons.max():.3f}')
                    grbs.close()
                except ImportError:
                    self.stdout.write('    (Install pygrib for detailed GRIB validation)')
                except Exception as e:
                    self.stdout.write(f'    GRIB validation skipped: {str(e)}')

            # For NetCDF files
            elif filepath.endswith('.nc'):
                with Dataset(filepath, 'r') as nc:
                    self.stdout.write(f'    Format: {getattr(nc, "data_model", "Unknown")}')
                    self.stdout.write(f'    Dimensions: {dict(nc.dimensions)}')
                    self.stdout.write(f'    Variables: {len(nc.variables)} variables')

                    # Check coordinate ranges
                    if 'latitude' in nc.variables:
                        lat = nc.variables['latitude'][:]
                        self.stdout.write(f'    Latitude range: {lat.min():.3f} to {lat.max():.3f}')
                    if 'longitude' in nc.variables:
                        lon = nc.variables['longitude'][:]
                        self.stdout.write(f'    Longitude range: {lon.min():.3f} to {lon.max():.3f}')

        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f'  Validation warning for {filepath}: {str(e)}')
            )

    def check_existing_files(self):
        """Check existing ERA5 files and report coverage"""
        if not os.path.exists(self.output_dir):
            self.stdout.write('No output directory found.')
            return
            
        files = [f for f in os.listdir(self.output_dir) if f.endswith('.nc')]
        files.sort()
        
        if not files:
            self.stdout.write('No ERA5 files found.')
            return
            
        self.stdout.write(f'Found {len(files)} ERA5 files in {self.output_dir}:')
        
        total_size = 0
        for filename in files:
            filepath = os.path.join(self.output_dir, filename)
            file_size = os.path.getsize(filepath)
            total_size += file_size
            
            # Extract date from filename
            try:
                if 'era5_swwa_' in filename:
                    date_part = filename.replace('era5_swwa_', '').replace('.nc', '')
                    if len(date_part) == 4:  # Year only
                        period = date_part
                    elif len(date_part) == 6:  # Year and month
                        period = f'{date_part[:4]}-{date_part[4:]}'
                    else:
                        period = date_part
                else:
                    period = 'Unknown'
            except:
                period = 'Unknown'
                
            self.stdout.write(
                f'  {filename} ({file_size / (1024*1024):.1f} MB) - {period}'
            )
            
        self.stdout.write(f'Total size: {total_size / (1024*1024*1024):.2f} GB')
        
        # Validate a sample file
        if files:
            sample_file = os.path.join(self.output_dir, files[0])
            self.stdout.write(f'\nSample file validation ({files[0]}):')
            self.validate_downloaded_file(sample_file)

    def test_era_request(self):
        """Test API connectivity with a small data request"""
        self.validate_cdsapi_credentials()
        
        test_year = 2023  # Use a year that should definitely be available
        test_filename = f'era5_test_{test_year}_01.nc'
        test_filepath = os.path.join(self.output_dir, test_filename)
        
        # Remove test file if it exists
        if os.path.exists(test_filepath):
            os.remove(test_filepath)
        
        self.stdout.write(f'Testing CDS API with small request for {test_year}-01-01...')
        
        try:
            c = cdsapi.Client()
            
            # Small test request matching the working CDS-generated format
            request = {
                'product_type': ['reanalysis'],
                'variable': ['2m_temperature'],
                'year': [str(test_year)],
                'month': ['01'],
                'day': ['01'],
                'time': ['12:00'],
                'data_format': 'netcdf',
                'download_format': 'unarchived',
                'area': [
                    self.boundaries['north'],
                    self.boundaries['west'], 
                    self.boundaries['south'],
                    self.boundaries['east']
                ]
            }
            
            c.retrieve('reanalysis-era5-single-levels', request, test_filepath)
            
            self.stdout.write(self.style.SUCCESS('✓ Test request successful!'))
            self.validate_downloaded_file(test_filepath)
            
            # Clean up test file
            if os.path.exists(test_filepath):
                os.remove(test_filepath)
                self.stdout.write('Test file cleaned up.')
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Test request failed: {str(e)}'))
            self.stdout.write(
                'This suggests there may be an issue with:\n'
                '  - Your CDS API credentials\n'
                '  - CDS system availability\n'
                '  - Network connectivity\n'
                '  - Data request format'
            )

    def test_small_request(self):
        """Test API connectivity with a small data request"""
        
        test_year = 2025
        test_filename = f'small_test_{test_year}_01.grib'
        test_filepath = os.path.join(self.output_dir, test_filename)
        
        # Remove test file if it exists
        if os.path.exists(test_filepath):
            os.remove(test_filepath)
        
        self.stdout.write(f'Testing CDS API with small request for {test_year}-01-01...')
        
        try:
            cds = cdsapi.Client()
            dataset = "reanalysis-era5-single-levels"
            request = {
                "product_type": ["reanalysis"],
                "variable": [
                    "10m_u_component_of_wind",
                    "10m_v_component_of_wind",
                    "2m_dewpoint_temperature",
                    "2m_temperature",
                    "sea_surface_temperature",
                    "surface_net_solar_radiation"
                    ],
                "year": [test_year],
                "month": ["01"],
                "day": ["01"],
                "time": [
                    "00:00", "01:00", "02:00",
                    "03:00", "04:00", "05:00",
                    "06:00", "07:00", "08:00",
                    "09:00", "10:00", "11:00",
                    "12:00", "13:00", "14:00",
                    "15:00", "16:00", "17:00",
                    "18:00", "19:00", "20:00",
                    "21:00", "22:00", "23:00"
                ],
                "data_format": "grib",
                "download_format": "unarchived",
                "area": [
                    self.boundaries['north'],
                    self.boundaries['west'], 
                    self.boundaries['south'],
                    self.boundaries['east']
                ],
            }

            cds.retrieve(dataset, request, test_filepath)
            self.stdout.write(self.style.SUCCESS('✓ Test request successful!'))
            self.validate_downloaded_file(test_filepath)
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Test request failed: {str(e)}'))

