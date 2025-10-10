# powerplot/management/commands/fetch_scada.py
from django.core.management.base import BaseCommand
from powerplotui.services.aemo_scada_fetcher import AEMOScadaFetcher
from datetime import datetime, date, timedelta
import pytz

class Command(BaseCommand):
    help = 'Fetch AEMO SCADA data for a specific trading day'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            type=str,
            help='Trading date in YYYY-MM-DD format (default: yesterday)',
        )
        parser.add_argument(
            '--days-back',
            type=int,
            help='Fetch data for N days back from today',
        )
        parser.add_argument(
            '--start-date',
            type=str,
            help='Start date for range fetch (YYYY-MM-DD)',
        )
        parser.add_argument(
            '--end-date',
            type=str,
            help='End date for range fetch (YYYY-MM-DD)',
        )
    
    def handle(self, *args, **options):
        fetcher = AEMOScadaFetcher()
        
        # Handle date range fetch
        if options['start_date'] and options['end_date']:
            start_date = datetime.strptime(options['start_date'], '%Y-%m-%d').date()
            end_date = datetime.strptime(options['end_date'], '%Y-%m-%d').date()
            
            self.stdout.write(f'Fetching SCADA data from {start_date} to {end_date}...')
            
            current_date = start_date
            total_count = 0
            
            while current_date <= end_date:
                try:
                    count = fetcher.fetch_latest_data(trading_date=current_date)
                    total_count += count
                    self.stdout.write(
                        self.style.SUCCESS(f'✓ {current_date}: {count} records')
                    )
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'✗ {current_date}: {str(e)}')
                    )
                
                current_date += timedelta(days=1)
            
            self.stdout.write(
                self.style.SUCCESS(f'\nTotal: {total_count} records fetched')
            )
            return
        
        # Handle days back
        if options['days_back']:
            end_date = date.today() - timedelta(days=1)
            start_date = end_date - timedelta(days=options['days_back'] - 1)
            
            self.stdout.write(f'Fetching SCADA data for last {options["days_back"]} days...')
            
            current_date = start_date
            total_count = 0
            
            while current_date <= end_date:
                try:
                    count = fetcher.fetch_latest_data(trading_date=current_date)
                    total_count += count
                    self.stdout.write(
                        self.style.SUCCESS(f'✓ {current_date}: {count} records')
                    )
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'✗ {current_date}: {str(e)}')
                    )
                
                current_date += timedelta(days=1)
            
            self.stdout.write(
                self.style.SUCCESS(f'\nTotal: {total_count} records fetched')
            )
            return
        
        # Handle specific date
        if options['date']:
            trading_date = datetime.strptime(options['date'], '%Y-%m-%d').date()
            self.stdout.write(f'Fetching SCADA data for {trading_date}...')
        else:
            # Default to yesterday
            awst = pytz.timezone('Australia/Perth')
            trading_date = (datetime.now(awst).date() - timedelta(days=1))
            self.stdout.write(f'Fetching SCADA data for yesterday ({trading_date})...')
        
        try:
            count = fetcher.fetch_latest_data(trading_date=trading_date)
            self.stdout.write(
                self.style.SUCCESS(f'Successfully fetched {count} records')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error: {str(e)}')
            )
            raise