# powerplot/management/commands/fetch_historical_scada.py
from django.core.management.base import BaseCommand
from powerplotui.services.aemo_scada_fetcher_bulk import AEMOScadaFetcher
from datetime import datetime, date
import json

class Command(BaseCommand):
    help = 'Fetch historical SCADA data from AEMO ZIP files'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            type=str,
            help='Single date to fetch (YYYY-MM-DD)',
        )
        parser.add_argument(
            '--month',
            type=str,
            help='Month to fetch in YYYY-MM format',
        )
        parser.add_argument(
            '--start-date',
            type=str,
            help='Start date for range (YYYY-MM-DD)',
        )
        parser.add_argument(
            '--end-date',
            type=str,
            help='End date for range (YYYY-MM-DD)',
        )
        parser.add_argument(
            '--year',
            type=int,
            help='Year to fetch (fetches all months in year)',
        )
        parser.add_argument(
            '--output-summary',
            type=str,
            help='Save summary to JSON file',
        )
    
    def handle(self, *args, **options):
        fetcher = AEMOScadaFetcher()
        
        # Single date
        if options['date']:
            trading_date = datetime.strptime(options['date'], '%Y-%m-%d').date()
            self.stdout.write(f'Fetching historical SCADA for {trading_date}...')
            
            try:
                count = fetcher.fetch_historical_data(trading_date)
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Successfully fetched {count:,} records')
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'✗ Error: {str(e)}')
                )
                raise
        
        # Single month
        elif options['month']:
            year, month = map(int, options['month'].split('-'))
            self.stdout.write(f'Fetching historical SCADA for {year}-{month:02d}...\n')
            
            summary = fetcher.fetch_month_historical(year, month)
            self._print_summary(summary)
            
            if options['output_summary']:
                self._save_summary(summary, options['output_summary'])
        
        # Date range
        elif options['start_date'] and options['end_date']:
            start_date = datetime.strptime(options['start_date'], '%Y-%m-%d').date()
            end_date = datetime.strptime(options['end_date'], '%Y-%m-%d').date()
            
            self.stdout.write(f'Fetching historical SCADA from {start_date} to {end_date}...\n')
            
            summary = fetcher.fetch_date_range_historical(start_date, end_date)
            self._print_summary(summary)
            
            if options['output_summary']:
                self._save_summary(summary, options['output_summary'])
        
        # Entire year
        elif options['year']:
            year = options['year']
            self.stdout.write(f'Fetching historical SCADA for entire year {year}...\n')
            
            all_summaries = []
            for month in range(1, 13):
                self.stdout.write(self.style.WARNING(f'\n--- Month {month}/12: {year}-{month:02d} ---'))
                summary = fetcher.fetch_month_historical(year, month)
                all_summaries.append(summary)
                self._print_summary(summary, compact=True)
            
            # Combined summary
            self._print_year_summary(all_summaries, year)
            
            if options['output_summary']:
                self._save_summary({
                    'year': year,
                    'months': all_summaries
                }, options['output_summary'])
        
        else:
            self.stdout.write(
                self.style.ERROR(
                    'Must specify one of: --date, --month, --start-date/--end-date, or --year'
                )
            )
    
    def _print_summary(self, summary, compact=False):
        """Print download summary"""
        if compact:
            self.stdout.write(
                f"  {summary.get('month', 'Range')}: "
                f"{summary['successful_days']}/{summary['total_days']} days, "
                f"{summary['total_records']:,} records"
            )
            if summary['failed_days'] > 0:
                self.stdout.write(
                    self.style.ERROR(f"  ⚠ {summary['failed_days']} failures")
                )
        else:
            # Build the period string separately to avoid nested f-strings
            if 'month' in summary:
                period = summary['month']
            else:
                start = summary.get('start_date', 'Unknown')
                end = summary.get('end_date', 'Unknown')
                period = f"{start} to {end}"
            
            self.stdout.write('\n' + '='*60)
            self.stdout.write(self.style.SUCCESS('DOWNLOAD SUMMARY'))
            self.stdout.write('='*60)
            self.stdout.write(f"Period: {period}")
            self.stdout.write(f"Total days: {summary['total_days']}")
            self.stdout.write(
                self.style.SUCCESS(f"✓ Successful: {summary['successful_days']}")
            )
            if summary.get('skipped_days', 0) > 0:
                self.stdout.write(
                    self.style.WARNING(f"⊘ Skipped: {summary['skipped_days']} (already existed)")
                )
            if summary['failed_days'] > 0:
                self.stdout.write(
                    self.style.ERROR(f"✗ Failed: {summary['failed_days']}")
                )
            self.stdout.write(f"Total records: {summary['total_records']:,}")
            
            if summary.get('errors'):
                self.stdout.write('\nErrors:')
                for error in summary['errors'][:5]:  # Show first 5
                    self.stdout.write(self.style.ERROR(f"  • {error}"))
                if len(summary['errors']) > 5:
                    self.stdout.write(f"  ... and {len(summary['errors']) - 5} more")
            
            self.stdout.write('='*60 + '\n')
    
    def _print_year_summary(self, summaries, year):
        """Print combined summary for entire year"""
        total_days = sum(s['total_days'] for s in summaries)
        total_successful = sum(s['successful_days'] for s in summaries)
        total_failed = sum(s['failed_days'] for s in summaries)
        total_records = sum(s['total_records'] for s in summaries)
        
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS(f'YEAR {year} SUMMARY'))
        self.stdout.write('='*60)
        self.stdout.write(f"Total days: {total_days}")
        self.stdout.write(self.style.SUCCESS(f"✓ Successful: {total_successful}"))
        if total_failed > 0:
            self.stdout.write(self.style.ERROR(f"✗ Failed: {total_failed}"))
        self.stdout.write(f"Total records: {total_records:,}")
        self.stdout.write('='*60 + '\n')
    
    def _save_summary(self, summary, filename):
        """Save summary to JSON file"""
        with open(filename, 'w') as f:
            json.dump(summary, f, indent=2, default=str)
        self.stdout.write(
            self.style.SUCCESS(f'Summary saved to {filename}')
        )