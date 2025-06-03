# Save this as: management/commands/get_era5_data.py

from django.core.management.base import BaseCommand, CommandError
import cdsapi
import calendar
import re

class Command(BaseCommand):
    help = 'Download ERA5 weather data for a specific month in 2024'

    def add_arguments(self, parser):
        parser.add_argument(
            'month',
            type=str,
            help='Month to download (format: "01", "02", ..., "12")'
        )

    def handle(self, *args, **options):
        month = options['month']
        
        # Validate month format
        if not re.match(r'^(0[1-9]|1[0-2])$', month):
            raise CommandError(
                'Month must be in format "01", "02", ..., "12". '
                f'You provided: "{month}"'
            )
        
        try:
            self.stdout.write(
                self.style.SUCCESS(f'Starting ERA5 data download for month {month}...')
            )
            
            # Get the number of days in the specified month for 2024
            year = 2024
            month_int = int(month)
            days_in_month = calendar.monthrange(year, month_int)[1]
            
            # Generate day list for the month
            days = [f"{day:02d}" for day in range(1, days_in_month + 1)]
            
            dataset = "reanalysis-era5-land"
            request = {
                "product_type": ["reanalysis"],
                "variable": [
                    "surface_net_solar_radiation",
                    "surface_solar_radiation_downwards"
                ],
                "year": ["2024"],
                "month": [month],
                "day": days,
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
                "data_format": "netcdf",
                "download_format": "unarchived",
                "area": [-28, 114, -35, 120]  # [North, West, South, East]
            }
            
            client = cdsapi.Client()
            filename = f"era5_data_2024_{month}.nc"
            
            self.stdout.write(f"Downloading data for {days_in_month} days...")
            self.stdout.write(f"Output file: {filename}")
            
            client.retrieve(dataset, request).download(filename)
            
            self.stdout.write(
                self.style.SUCCESS(f'Successfully downloaded ERA5 data to: {filename}')
            )
            
        except Exception as e:
            raise CommandError(f'Error downloading ERA5 data: {str(e)}')
        