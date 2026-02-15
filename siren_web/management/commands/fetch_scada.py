# powerplot/management/commands/fetch_scada.py
from django.core.management.base import BaseCommand
from powerplotui.services.aemo_scada_fetcher import AEMOScadaFetcher
from datetime import datetime, date, timedelta
import pytz
import json


class Command(BaseCommand):
    help = 'Fetch AEMO SCADA data from current JSON files or historical ZIP archives'
    
    def add_arguments(self, parser):
        # Mode selection
        parser.add_argument(
            '--historical',
            action='store_true',
            help='Fetch from historical ZIP archives instead of current JSON files',
        )
        
        # Date options (work in both modes)
        parser.add_argument(
            '--date',
            type=str,
            help='Single date to fetch (YYYY-MM-DD)',
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
        
        # Current mode options
        parser.add_argument(
            '--days-back',
            type=int,
            help='Fetch data for N days back from today (current mode only)',
        )
        
        # Historical mode options
        parser.add_argument(
            '--month',
            type=str,
            help='Month to fetch in YYYY-MM format (historical mode only)',
        )
        parser.add_argument(
            '--year',
            type=int,
            help='Year to fetch - fetches all months (historical mode only)',
        )
        
        # Backfill options
        parser.add_argument(
            '--backfill-peak-re',
            action='store_true',
            help='Backfill DailyPeakRE from existing half-hourly SCADA data for days missing peak RE records',
        )

        # Output options
        parser.add_argument(
            '--output-summary',
            type=str,
            help='Save summary to JSON file',
        )
    
    def handle(self, *args, **options):
        fetcher = AEMOScadaFetcher()

        # Handle backfill mode
        if options['backfill_peak_re']:
            self._handle_backfill(fetcher, options)
            return

        historical = options['historical']

        # Validate mode-specific options
        if not historical and (options['month'] or options['year']):
            self.stdout.write(
                self.style.WARNING(
                    'Note: --month and --year require --historical flag. Adding it automatically.'
                )
            )
            historical = True
        
        if historical and options['days_back']:
            self.stdout.write(
                self.style.ERROR('--days-back is not available in historical mode')
            )
            return
        
        mode_label = 'historical' if historical else 'current'
        
        # Route to appropriate handler
        if historical:
            self._handle_historical(fetcher, options)
        else:
            self._handle_current(fetcher, options)
    
    def _handle_backfill(self, fetcher, options):
        """Backfill DailyPeakRE from existing half-hourly SCADA data"""
        from calendar import monthrange
        from siren_web.models import FacilityScada

        if options['start_date'] and options['end_date']:
            start = datetime.strptime(options['start_date'], '%Y-%m-%d').date()
            end = datetime.strptime(options['end_date'], '%Y-%m-%d').date()
        elif options.get('month'):
            year, month = map(int, options['month'].split('-'))
            start = date(year, month, 1)
            _, last = monthrange(year, month)
            end = date(year, month, last)
        else:
            earliest = FacilityScada.objects.order_by('dispatch_interval').first()
            if not earliest:
                self.stdout.write(self.style.ERROR('No SCADA data found'))
                return
            start = earliest.dispatch_interval.date()
            end = date.today() - timedelta(days=1)

        self.stdout.write(f'Backfilling DailyPeakRE from {start} to {end}...')
        summary = fetcher.backfill_daily_peak_re(start, end)
        self.stdout.write(
            self.style.SUCCESS(
                f'Backfilled {summary["backfilled"]} days, '
                f'skipped {summary["skipped"]} days'
            )
        )

    def _handle_current(self, fetcher, options):
        """Handle current/recent SCADA data fetching"""
        
        # Date range
        if options['start_date'] and options['end_date']:
            start_date = datetime.strptime(options['start_date'], '%Y-%m-%d').date()
            end_date = datetime.strptime(options['end_date'], '%Y-%m-%d').date()
            
            self.stdout.write(f'Fetching current SCADA data from {start_date} to {end_date}...')
            summary = self._fetch_current_range(fetcher, start_date, end_date)
            self._print_summary(summary)
            
            if options['output_summary']:
                self._save_summary(summary, options['output_summary'])
            return
        
        # Days back
        if options['days_back']:
            end_date = date.today() - timedelta(days=1)
            start_date = end_date - timedelta(days=options['days_back'] - 1)
            
            self.stdout.write(f'Fetching current SCADA data for last {options["days_back"]} days...')
            summary = self._fetch_current_range(fetcher, start_date, end_date)
            self._print_summary(summary)
            
            if options['output_summary']:
                self._save_summary(summary, options['output_summary'])
            return
        
        # Single date or default to yesterday
        if options['date']:
            trading_date = datetime.strptime(options['date'], '%Y-%m-%d').date()
            self.stdout.write(f'Fetching current SCADA data for {trading_date}...')
        else:
            awst = pytz.timezone('Australia/Perth')
            trading_date = datetime.now(awst).date() - timedelta(days=1)
            self.stdout.write(f'Fetching current SCADA data for yesterday ({trading_date})...')
        
        try:
            count = fetcher.fetch_latest_data(trading_date=trading_date)
            self.stdout.write(
                self.style.SUCCESS(f'✓ Successfully fetched {count:,} records')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'✗ Error: {str(e)}')
            )
            raise
    
    def _fetch_current_range(self, fetcher, start_date, end_date):
        """Fetch current data for a date range with summary tracking"""
        current_date = start_date
        summary = {
            'start_date': str(start_date),
            'end_date': str(end_date),
            'total_days': 0,
            'successful_days': 0,
            'failed_days': 0,
            'total_records': 0,
            'errors': []
        }
        
        while current_date <= end_date:
            summary['total_days'] += 1
            try:
                count = fetcher.fetch_latest_data(trading_date=current_date)
                summary['total_records'] += count
                summary['successful_days'] += 1
                self.stdout.write(
                    self.style.SUCCESS(f'  ✓ {current_date}: {count:,} records')
                )
            except Exception as e:
                summary['failed_days'] += 1
                error_msg = f'{current_date}: {str(e)}'
                summary['errors'].append(error_msg)
                self.stdout.write(
                    self.style.ERROR(f'  ✗ {current_date}: {str(e)}')
                )
            
            current_date += timedelta(days=1)
        
        return summary
    
    def _handle_historical(self, fetcher, options):
        """Handle historical SCADA data fetching from ZIP archives"""
        
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
            return
        
        # Single month
        if options['month']:
            year, month = map(int, options['month'].split('-'))
            self.stdout.write(f'Fetching historical SCADA for {year}-{month:02d}...\n')
            
            summary = fetcher.fetch_month_historical(year, month)
            self._print_summary(summary)
            
            if options['output_summary']:
                self._save_summary(summary, options['output_summary'])
            return
        
        # Date range
        if options['start_date'] and options['end_date']:
            start_date = datetime.strptime(options['start_date'], '%Y-%m-%d').date()
            end_date = datetime.strptime(options['end_date'], '%Y-%m-%d').date()
            
            self.stdout.write(f'Fetching historical SCADA from {start_date} to {end_date}...\n')
            
            summary = fetcher.fetch_date_range_historical(start_date, end_date)
            self._print_summary(summary)
            
            if options['output_summary']:
                self._save_summary(summary, options['output_summary'])
            return
        
        # Entire year
        if options['year']:
            year = options['year']
            self.stdout.write(f'Fetching historical SCADA for entire year {year}...\n')
            
            all_summaries = []
            for month in range(1, 13):
                self.stdout.write(
                    self.style.WARNING(f'\n--- Month {month}/12: {year}-{month:02d} ---')
                )
                summary = fetcher.fetch_month_historical(year, month)
                all_summaries.append(summary)
                self._print_summary(summary, compact=True)
            
            self._print_year_summary(all_summaries, year)
            
            if options['output_summary']:
                self._save_summary({
                    'year': year,
                    'months': all_summaries
                }, options['output_summary'])
            return
        
        # No valid historical option specified
        self.stdout.write(
            self.style.ERROR(
                'Historical mode requires: --date, --month, --start-date/--end-date, or --year'
            )
        )
    
    def _print_summary(self, summary, compact=False):
        """Print download summary"""
        if compact:
            period = summary.get('month', 'Range')
            self.stdout.write(
                f"  {period}: "
                f"{summary['successful_days']}/{summary['total_days']} days, "
                f"{summary['total_records']:,} records"
            )
            if summary['failed_days'] > 0:
                self.stdout.write(
                    self.style.ERROR(f"  ⚠ {summary['failed_days']} failures")
                )
        else:
            if 'month' in summary:
                period = summary['month']
            else:
                start = summary.get('start_date', 'Unknown')
                end = summary.get('end_date', 'Unknown')
                period = f"{start} to {end}"
            
            self.stdout.write('\n' + '=' * 60)
            self.stdout.write(self.style.SUCCESS('DOWNLOAD SUMMARY'))
            self.stdout.write('=' * 60)
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
                for error in summary['errors'][:5]:
                    self.stdout.write(self.style.ERROR(f"  • {error}"))
                if len(summary['errors']) > 5:
                    self.stdout.write(f"  ... and {len(summary['errors']) - 5} more")
            
            self.stdout.write('=' * 60 + '\n')
    
    def _print_year_summary(self, summaries, year):
        """Print combined summary for entire year"""
        total_days = sum(s['total_days'] for s in summaries)
        total_successful = sum(s['successful_days'] for s in summaries)
        total_failed = sum(s['failed_days'] for s in summaries)
        total_skipped = sum(s.get('skipped_days', 0) for s in summaries)
        total_records = sum(s['total_records'] for s in summaries)
        
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS(f'YEAR {year} SUMMARY'))
        self.stdout.write('=' * 60)
        self.stdout.write(f"Total days: {total_days}")
        self.stdout.write(self.style.SUCCESS(f"✓ Successful: {total_successful}"))
        if total_skipped > 0:
            self.stdout.write(self.style.WARNING(f"⊘ Skipped: {total_skipped}"))
        if total_failed > 0:
            self.stdout.write(self.style.ERROR(f"✗ Failed: {total_failed}"))
        self.stdout.write(f"Total records: {total_records:,}")
        self.stdout.write('=' * 60 + '\n')
    
    def _save_summary(self, summary, filename):
        """Save summary to JSON file"""
        with open(filename, 'w') as f:
            json.dump(summary, f, indent=2, default=str)
        self.stdout.write(
            self.style.SUCCESS(f'Summary saved to {filename}')
        )