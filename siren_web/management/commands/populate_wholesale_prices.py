"""
Django management command to populate WholesalePrice model from AEMO data.

Downloads dated files from AEMO directory and processes them.

Data sources:
    --yesterday: Uses current endpoint (uncompressed JSON, ideal for cron jobs)
        https://data.wa.aemo.com.au/public/market-data/wemde/referenceTradingPrice/current/
    
    Other options: Uses previous endpoint (ZIP archives)
        https://data.wa.aemo.com.au/public/market-data/wemde/referenceTradingPrice/previous/

Usage:
    python manage.py populate_wholesale_prices --date 2025-10-24
    python manage.py populate_wholesale_prices --start-date 2025-10-20 --end-date 2025-10-24
    python manage.py populate_wholesale_prices --yesterday      # Uses current endpoint (for cron)
    python manage.py populate_wholesale_prices --last-7-days
    python manage.py populate_wholesale_prices --last-30-days
"""
import json
import zipfile
import requests
import pytz
from io import BytesIO
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand, CommandError
from django.utils.dateparse import parse_datetime
from siren_web.services.wholesale_price_matrix import clear_range, set_price_values

AWST = pytz.timezone('Australia/Perth')


class Command(BaseCommand):
    help = 'Fetch and populate wholesale prices from AEMO data for specific dates'

    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            type=str,
            help='Specific date to fetch (YYYY-MM-DD)',
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
            '--yesterday',
            action='store_true',
            help='Fetch yesterday\'s data',
        )
        parser.add_argument(
            '--last-7-days',
            action='store_true',
            help='Fetch last 7 days of data',
        )
        parser.add_argument(
            '--last-30-days',
            action='store_true',
            help='Fetch last 30 days of data',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force update existing records',
        )

    def handle(self, *args, **options):
        force_update = options['force']
        use_current = options['yesterday']  # Use current endpoint for yesterday's data
        
        # Determine which dates to fetch
        dates_to_fetch = self.get_dates_to_fetch(options)
        
        if not dates_to_fetch:
            raise CommandError('No dates specified. Use --date, --start-date/--end-date, --yesterday, or --last-7-days')
        
        self.stdout.write(self.style.SUCCESS(
            f'Starting wholesale price import for {len(dates_to_fetch)} date(s)...'
        ))
        
        # Use different endpoints for current vs previous data
        if use_current:
            base_url = 'https://data.wa.aemo.com.au/public/market-data/wemde/referenceTradingPrice/current'
        else:
            base_url = 'https://data.wa.aemo.com.au/public/market-data/wemde/referenceTradingPrice/previous'
        
        total_saved = 0
        successful = 0
        failed = 0
        
        for fetch_date in dates_to_fetch:
            self.stdout.write('\n' + '='*80)
            self.stdout.write(f'Processing date: {fetch_date}')
            self.stdout.write('='*80)
            
            try:
                # Construct filename - current endpoint uses .json, previous uses .zip
                if use_current:
                    filename = f'ReferenceTradingPrice_{fetch_date.strftime("%Y-%m-%d")}.json'
                else:
                    filename = f'ReferenceTradingPrice_{fetch_date.strftime("%Y%m%d")}.zip'
                file_url = f'{base_url}/{filename}'
                
                self.stdout.write(f'Downloading: {file_url}')
                
                # Download and process the file
                saved_count = self.download_and_process(file_url, force_update, is_json=use_current)
                
                total_saved += saved_count
                successful += 1
                
                self.stdout.write(self.style.SUCCESS(
                    f'✓ Successfully imported {saved_count} records for {fetch_date}'
                ))
                
            except Exception as e:
                failed += 1
                self.stdout.write(self.style.ERROR(
                    f'✗ Failed to process {fetch_date}: {str(e)}'
                ))
        
        # Summary
        self.stdout.write('\n' + '='*80)
        self.stdout.write(self.style.SUCCESS('SUMMARY'))
        self.stdout.write('='*80)
        self.stdout.write(f'Total dates processed: {len(dates_to_fetch)}')
        self.stdout.write(f'Successful: {successful}')
        self.stdout.write(f'Failed: {failed}')
        self.stdout.write(f'Total records saved: {total_saved}')
        
        if failed > 0:
            self.stdout.write(self.style.WARNING(
                f'\n⚠ {failed} date(s) failed. Check if files exist for those dates.'
            ))

    def get_dates_to_fetch(self, options):
        """Determine which dates to fetch based on command options."""
        dates = []
        
        if options['date']:
            # Single date
            dates.append(datetime.strptime(options['date'], '%Y-%m-%d').date())
            
        elif options['start_date'] and options['end_date']:
            # Date range
            start = datetime.strptime(options['start_date'], '%Y-%m-%d').date()
            end = datetime.strptime(options['end_date'], '%Y-%m-%d').date()
            
            if start > end:
                raise CommandError('start-date must be before end-date')
            
            current = start
            while current <= end:
                dates.append(current)
                current += timedelta(days=1)
                
        elif options['yesterday']:
            # Yesterday
            dates.append(datetime.now().date() - timedelta(days=1))
            
        elif options['last_7_days']:
            # Last 7 days
            today = datetime.now().date()
            for i in range(1, 8):
                dates.append(today - timedelta(days=i))
                
        elif options['last_30_days']:
            # Last 30 days
            today = datetime.now().date()
            for i in range(1, 31):
                dates.append(today - timedelta(days=i))
        
        # Sort dates
        dates.sort()
        
        return dates

    def download_and_process(self, url, force_update=False, is_json=False):
        """Download a file and process it.
        
        Args:
            url: URL to download
            force_update: Whether to force update existing records
            is_json: If True, expect plain JSON file; if False, expect ZIP archive
        """
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        }
        
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        # Check content type
        content_type = response.headers.get('Content-Type', '')
        self.stdout.write(f'Content-Type: {content_type}')
        self.stdout.write(f'Size: {len(response.content)} bytes')
        
        if is_json:
            # Process plain JSON file
            try:
                data = response.json()
            except json.JSONDecodeError as e:
                raise CommandError(f'Failed to parse JSON: {e}')
        else:
            # Process ZIP file
            try:
                with zipfile.ZipFile(BytesIO(response.content)) as zip_file:
                    # Get JSON files
                    json_files = [f for f in zip_file.namelist() if f.endswith('.json')]
                    
                    if not json_files:
                        raise CommandError('No JSON files found in ZIP archive')
                    
                    self.stdout.write(f'Found {len(json_files)} JSON file(s) in archive')
                    
                    # Process the first JSON file
                    with zip_file.open(json_files[0]) as json_file:
                        data = json.load(json_file)
                        
            except zipfile.BadZipFile:
                raise CommandError('Downloaded file is not a valid ZIP archive')
        
        # Process and save data
        saved_count = self.process_data(data, force_update)
        
        return saved_count

    def process_data(self, data, force_update=False):
        """Process JSON data and save to database."""
        
        # Handle array-wrapped format: [{"data": {...}}]
        if isinstance(data, list):
            if not data:
                raise CommandError('Invalid data structure: empty array')
            data = data[0]
        
        if 'data' not in data:
            raise CommandError('Invalid data structure: missing "data" key')
        
        trading_day = data['data'].get('tradingDay')
        prices = data['data'].get('referenceTradingPrices', [])
        
        if not trading_day or not prices:
            raise CommandError('Invalid data structure: missing tradingDay or prices')
        
        self.stdout.write(f'Processing {len(prices)} price records for {trading_day}...')
        
        # Parse trading day
        trading_date = datetime.strptime(trading_day, '%Y-%m-%d').date()

        # Prepare records for the matrix writer
        wholesale_prices = []
        skipped_unpublished = 0

        for price_data in prices:
            if not price_data.get('isPublished', False):
                skipped_unpublished += 1
                continue  # Skip unpublished prices

            trading_interval_str = price_data.get('tradingInterval')
            wholesale_price = price_data.get('referenceTradingPrice')

            if not trading_interval_str or wholesale_price is None:
                continue

            # Parse trading interval datetime
            trading_interval = parse_datetime(trading_interval_str)

            if not trading_interval:
                self.stdout.write(self.style.WARNING(
                    f'Failed to parse interval: {trading_interval_str}'
                ))
                continue

            wholesale_prices.append({
                'trading_interval': trading_interval,
                'wholesale_price': wholesale_price,
            })

        if skipped_unpublished > 0:
            self.stdout.write(f'Skipped {skipped_unpublished} unpublished records')

        if not wholesale_prices:
            self.stdout.write(self.style.WARNING('No valid price records to save'))
            return 0

        # Show price statistics
        prices_values = [p['wholesale_price'] for p in wholesale_prices]
        self.stdout.write(f'Price range: ${min(prices_values):.2f} - ${max(prices_values):.2f}/MWh')
        self.stdout.write(f'Average: ${sum(prices_values)/len(prices_values):.2f}/MWh')

        if force_update:
            # Clear the whole AWST trading day first, matching the old
            # delete-then-recreate semantics -- handles AEMO retracting a
            # previously-published interval on a re-fetch, which a plain
            # patch-in-place write (below) would otherwise leave stale.
            day_start_awst = AWST.localize(datetime.combine(trading_date, datetime.min.time()))
            clear_range(day_start_awst, day_start_awst + timedelta(days=1))

        set_price_values(wholesale_prices)
        saved_count = len(wholesale_prices)

        return saved_count