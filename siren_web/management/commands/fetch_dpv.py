# powerplot/management/commands/fetch_dpv.py
from django.core.management.base import BaseCommand
from powerplotui.services.dpv_fetcher import DPVDataFetcher
from datetime import datetime

class Command(BaseCommand):
    help = 'Fetch DPV generation data from AEMO'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--year',
            type=int,
            help='Year to fetch',
        )
        parser.add_argument(
            '--month',
            type=int,
            help='Month to fetch (1-12)',
        )
        parser.add_argument(
            '--start-year',
            type=int,
            help='Start year for range fetch',
        )
        parser.add_argument(
            '--end-year',
            type=int,
            help='End year for range fetch',
        )
    
    def handle(self, *args, **options):
        fetcher = DPVDataFetcher()
        
        # Fetch year range
        if options['start_year'] and options['end_year']:
            self.stdout.write(
                f"Fetching DPV data from {options['start_year']} to {options['end_year']}..."
            )
            
            total = 0
            for year in range(options['start_year'], options['end_year'] + 1):
                try:
                    self.stdout.write(f"\nFetching year {year}...")
                    count = fetcher.fetch_year(year)
                    total += count
                    self.stdout.write(
                        self.style.SUCCESS(f"✓ {year}: {count:,} records")
                    )
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"✗ {year}: {str(e)}")
                    )
            
            self.stdout.write(
                self.style.SUCCESS(f"\nTotal: {total:,} records fetched")
            )
            return
        
        # Fetch single year
        if options['year'] and not options['month']:
            year = options['year']
            self.stdout.write(f"Fetching DPV data for year {year}...")
            
            try:
                count = fetcher.fetch_year(year)
                self.stdout.write(
                    self.style.SUCCESS(f"✓ Successfully fetched {count:,} records")
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"✗ Error: {str(e)}")
                )
                raise
            return
        
        # Fetch specific month
        if options['year'] and options['month']:
            year = options['year']
            month = options['month']
            
            if not 1 <= month <= 12:
                self.stdout.write(
                    self.style.ERROR('Month must be between 1 and 12')
                )
                return
            
            self.stdout.write(f"Fetching DPV data for {year}-{month:02d}...")
            
            try:
                count = fetcher.fetch_dpv_data(year, month)
                self.stdout.write(
                    self.style.SUCCESS(f"✓ Successfully fetched {count:,} records")
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"✗ Error: {str(e)}")
                )
                raise
        else:
            # Default to current month
            now = datetime.now()
            self.stdout.write(
                f"Fetching DPV data for current month ({now.year}-{now.month:02d})..."
            )
            
            try:
                count = fetcher.fetch_dpv_data(now.year, now.month)
                self.stdout.write(
                    self.style.SUCCESS(f"✓ Successfully fetched {count:,} records")
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"✗ Error: {str(e)}")
                )
                raise