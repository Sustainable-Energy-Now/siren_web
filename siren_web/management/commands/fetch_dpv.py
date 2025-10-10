# powerplot/management/commands/fetch_dpv.py
from django.core.management.base import BaseCommand
from powerplot.services.dpv_fetcher import DPVDataFetcher
from datetime import datetime

class Command(BaseCommand):
    help = 'Fetch DPV generation data from AEMO'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--year',
            type=int,
            help='Year to fetch (default: current year)',
        )
        parser.add_argument(
            '--month',
            type=int,
            help='Month to fetch (default: current month)',
        )
        parser.add_argument(
            '--backfill',
            action='store_true',
            help='Backfill data from start date to end date',
        )
        parser.add_argument(
            '--start-year',
            type=int,
            help='Start year for backfill',
        )
        parser.add_argument(
            '--start-month',
            type=int,
            help='Start month for backfill',
        )
        parser.add_argument(
            '--end-year',
            type=int,
            help='End year for backfill',
        )
        parser.add_argument(
            '--end-month',
            type=int,
            help='End month for backfill',
        )
    
    def handle(self, *args, **options):
        fetcher = DPVDataFetcher()
        
        if options['backfill']:
            if not all([
                options['start_year'],
                options['start_month'],
                options['end_year'],
                options['end_month']
            ]):
                self.stdout.write(
                    self.style.ERROR(
                        'Backfill requires --start-year, --start-month, --end-year, --end-month'
                    )
                )
                return
            
            start_date = datetime(options['start_year'], options['start_month'], 1)
            end_date = datetime(options['end_year'], options['end_month'], 1)
            
            self.stdout.write(f'Backfilling DPV data from {start_date} to {end_date}...')
            total = fetcher.fetch_date_range(start_date, end_date)
            self.stdout.write(
                self.style.SUCCESS(f'Successfully fetched {total} total records')
            )
        else:
            year = options.get('year')
            month = options.get('month')
            
            if year and month:
                self.stdout.write(f'Fetching DPV data for {year}-{month:02d}...')
            else:
                self.stdout.write('Fetching DPV data for current month...')
            
            count = fetcher.fetch_dpv_data(year, month)
            self.stdout.write(
                self.style.SUCCESS(f'Successfully fetched {count} records')
            )