# powerplot/services/aemo_scada_fetcher.py
import requests
import json
import zipfile
import io
from datetime import datetime, timedelta, date
from decimal import Decimal
from collections import defaultdict
from django.db import transaction, connection
from django.utils import timezone
import pytz
from siren_web.models import FacilityScada, facilities, Technologies
import logging
import time

logger = logging.getLogger(__name__)

class AEMOScadaFetcher:
    CURRENT_URL = "https://data.wa.aemo.com.au/public/market-data/wemde/facilityScada/current/"
    HISTORICAL_URL = "https://data.wa.aemo.com.au/public/market-data/wemde/facilityScada/previous/"
    AWST = pytz.timezone('Australia/Perth')
    
    def __init__(self):
        # Cache facility lookups to avoid repeated DB queries
        self._facility_cache = {}
        self._load_facility_cache()
    
    def _load_facility_cache(self):
        """Load all facilities into cache for faster lookups"""
        all_facilities = facilities.objects.filter(active=True).values(
            'idfacilities', 'facility_code'
        )
        
        self._facility_cache = {
            f['facility_code']: f['idfacilities'] 
            for f in all_facilities
        }
        
        logger.info(f"Loaded {len(self._facility_cache)} facilities into cache")
    
    def _get_facility_id(self, facility_code):
        """
        Get facility ID from code, with caching
        Creates facility if it doesn't exist
        """
        # Check cache first
        if facility_code in self._facility_cache:
            return self._facility_cache[facility_code]
        
        # Try to get from database
        try:
            facility = facilities.objects.get(facility_code=facility_code)
            self._facility_cache[facility_code] = facility.idfacilities
            return facility.idfacilities
        except facilities.DoesNotExist:
            logger.warning(f"Facility '{facility_code}' not found. Creating placeholder.")
            return self._create_placeholder_facility(facility_code)
    
    def _create_placeholder_facility(self, facility_code):
        """Create a placeholder facility for unknown codes"""
        
        # Get or create 'Unknown' technology
        unknown_tech, _ = Technologies.objects.get_or_create(
            technology_name='Unknown',
            defaults={'technology_signature': 'UNK','category': 'Generator', 'renewable': '0', 'dispatchable':'0','fuel_type': 'Unknown'}
        )
        
        # Create facility
        facility = facilities.objects.create(
            facility_name=f'Auto-created: {facility_code}',
            facility_code=facility_code,
            active=True,
            existing=True,
            idtechnologies=unknown_tech
        )
        
        # Add to cache
        self._facility_cache[facility_code] = facility.idfacilities
        logger.info(f"Created placeholder facility for '{facility_code}'")
        
        return facility.idfacilities
    
    def fetch_latest_data(self, trading_date=None):
        """
        Fetch SCADA data for a trading day from current directory
        trading_date: datetime.date object, defaults to yesterday
        """
        if trading_date is None:
            trading_date = (timezone.now().astimezone(self.AWST).date() - 
                          timedelta(days=1))
        
        # Current data uses: SCADA_2025-10-05.json
        url = f"{self.CURRENT_URL}SCADA_{trading_date.strftime('%Y-%m-%d')}.json"
        
        try:
            logger.info(f"Fetching current SCADA data from {url}")
            response = requests.get(url, timeout=60)
            response.raise_for_status()
            
            data = response.json()
            records = self._parse_data(data)
            saved_count = self._save_data(records)
            
            logger.info(f"Successfully saved {saved_count} SCADA records for {trading_date}")
            return saved_count
            
        except requests.RequestException as e:
            logger.error(f"Error fetching SCADA data from {url}: {e}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing JSON from {url}: {e}")
            raise
    
    def fetch_historical_data(self, trading_date):
        """
        Fetch historical SCADA data for a single day from ZIP file
        Historical data uses: FacilityScada_20240101.zip
        
        Args:
            trading_date: datetime.date object
        
        Returns:
            int: number of records saved
        """
        # Historical filename format: FacilityScada_20240101.zip
        filename = f"FacilityScada_{trading_date.strftime('%Y%m%d')}.zip"
        url = f"{self.HISTORICAL_URL}{filename}"
        
        try:
            logger.info(f"Fetching historical SCADA data from {url}")
            response = requests.get(url, timeout=120)
            response.raise_for_status()
            
            # Extract and process ZIP file
            records = self._process_zip_file(response.content, trading_date)
            saved_count = self._save_data(records)
            
            logger.info(f"Successfully saved {saved_count} historical SCADA records for {trading_date}")
            return saved_count
            
        except requests.RequestException as e:
            logger.error(f"Error fetching historical SCADA from {url}: {e}")
            raise
        except zipfile.BadZipFile as e:
            logger.error(f"Invalid ZIP file from {url}: {e}")
            raise
    
    def _process_zip_file(self, zip_content, trading_date):
        """
        Extract and process JSON from ZIP file
        
        Args:
            zip_content: bytes content of ZIP file
            trading_date: date for logging purposes
        
        Returns:
            list: parsed records
        """
        records = []
        
        with zipfile.ZipFile(io.BytesIO(zip_content)) as zf:
            # List files in ZIP
            file_list = zf.namelist()
            logger.info(f"ZIP contains {len(file_list)} files: {file_list}")
            
            # Process each JSON file in the ZIP
            for filename in file_list:
                if filename.endswith('.json'):
                    logger.info(f"Processing {filename}")
                    
                    with zf.open(filename) as json_file:
                        data = json.load(json_file)
                        file_records = self._parse_data(data)
                        records.extend(file_records)
                        logger.info(f"Extracted {len(file_records)} records from {filename}")
        
        logger.info(f"Total records from ZIP: {len(records)}")
        return records
    
    def fetch_month_historical(self, year, month):
        """
        Fetch historical SCADA data for an entire month
        
        Args:
            year: int (e.g., 2024)
            month: int (1-12)
        
        Returns:
            dict: summary of downloads
        """
        start_date = date(year, month, 1)
        
        # Get last day of month
        if month == 12:
            end_date = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(year, month + 1, 1) - timedelta(days=1)
        
        logger.info(f"Fetching historical SCADA for {year}-{month:02d} ({start_date} to {end_date})")
        
        current_date = start_date
        summary = {
            'month': f"{year}-{month:02d}",
            'total_days': 0,
            'successful_days': 0,
            'failed_days': 0,
            'total_records': 0,
            'errors': []
        }
        
        while current_date <= end_date:
            summary['total_days'] += 1
            
            try:
                # Check if data already exists
                exists, existing_count = self.verify_data_exists(current_date)
                
                if exists:
                    logger.info(f"✓ {current_date}: Data already exists ({existing_count:,} records), skipping")
                    summary['successful_days'] += 1
                    summary['total_records'] += existing_count
                else:
                    # Fetch data
                    count = self.fetch_historical_data(current_date)
                    summary['successful_days'] += 1
                    summary['total_records'] += count
                    logger.info(f"✓ {current_date}: Fetched {count:,} records")
                
                # Small delay to be nice to the server
                time.sleep(0.5)
                
            except Exception as e:
                summary['failed_days'] += 1
                error_msg = f"{current_date}: {str(e)}"
                summary['errors'].append(error_msg)
                logger.error(f"✗ {error_msg}")
            
            current_date += timedelta(days=1)
        
        logger.info(
            f"Month summary: {summary['successful_days']}/{summary['total_days']} days successful, "
            f"{summary['total_records']:,} total records"
        )
        
        return summary
    
    def fetch_date_range_historical(self, start_date, end_date):
        """
        Fetch historical SCADA data for a date range
        
        Args:
            start_date: datetime.date
            end_date: datetime.date
        
        Returns:
            dict: summary of downloads
        """
        logger.info(f"Fetching historical SCADA from {start_date} to {end_date}")
        
        current_date = start_date
        summary = {
            'start_date': str(start_date),
            'end_date': str(end_date),
            'total_days': 0,
            'successful_days': 0,
            'failed_days': 0,
            'skipped_days': 0,
            'total_records': 0,
            'errors': []
        }
        
        while current_date <= end_date:
            summary['total_days'] += 1
            
            try:
                # Check if data already exists
                exists, existing_count = self.verify_data_exists(current_date)
                
                if exists:
                    logger.info(f"⊘ {current_date}: Already exists ({existing_count:,} records), skipping")
                    summary['skipped_days'] += 1
                    summary['total_records'] += existing_count
                else:
                    # Fetch data
                    count = self.fetch_historical_data(current_date)
                    summary['successful_days'] += 1
                    summary['total_records'] += count
                    logger.info(f"✓ {current_date}: Fetched {count:,} records")
                
                # Progress update every 7 days
                if summary['total_days'] % 7 == 0:
                    logger.info(
                        f"Progress: {summary['total_days']} days processed, "
                        f"{summary['total_records']:,} total records"
                    )
                
                # Small delay between requests
                time.sleep(0.5)
                
            except Exception as e:
                summary['failed_days'] += 1
                error_msg = f"{current_date}: {str(e)}"
                summary['errors'].append(error_msg)
                logger.error(f"✗ {error_msg}")
            
            current_date += timedelta(days=1)
        
        logger.info(
            f"\n{'='*60}\n"
            f"Historical fetch complete!\n"
            f"Total days: {summary['total_days']}\n"
            f"Successful: {summary['successful_days']}\n"
            f"Skipped: {summary['skipped_days']}\n"
            f"Failed: {summary['failed_days']}\n"
            f"Total records: {summary['total_records']:,}\n"
            f"{'='*60}"
        )
        
        return summary
    
    def _parse_data(self, data):
        """Parse JSON response into list of records"""
        records = []
        
        if 'data' in data and 'facilityScadaDispatchIntervals' in data['data']:
            scada_records = data['data']['facilityScadaDispatchIntervals']
        elif 'facilityScadaDispatchIntervals' in data:
            scada_records = data['facilityScadaDispatchIntervals']
        elif isinstance(data, list):
            scada_records = data
        else:
            logger.error(f"Unknown JSON structure. Keys: {data.keys() if isinstance(data, dict) else 'not a dict'}")
            raise ValueError(f"Unknown JSON structure in response")
        
        for item in scada_records:
            try:
                dispatch_interval_str = item.get('dispatchInterval') or item.get('dispatch_interval')
                
                if not dispatch_interval_str:
                    continue
                
                dispatch_interval = datetime.fromisoformat(dispatch_interval_str)
                
                facility_code = item.get('code') or item.get('facilityCode') or item.get('facility_code')
                
                if not facility_code:
                    continue
                
                quantity = item.get('quantity') or item.get('mw')
                
                if quantity is None:
                    continue
                
                # Get facility ID from code
                facility_id = self._get_facility_id(facility_code)
                
                records.append({
                    'dispatch_interval': dispatch_interval,
                    'facility_id': facility_id,
                    'quantity': Decimal(str(quantity))
                })
                
            except (ValueError, KeyError, TypeError) as e:
                logger.warning(f"Error parsing record: {item}. Error: {e}")
                continue
        
        logger.debug(f"Parsed {len(records)} records from JSON")
        return records
    
    def _aggregate_to_hourly(self, records):
        """
        Aggregate 5-minute dispatch intervals into hourly averages.
        
        For power generation data, we average the MW values across the 
        12 five-minute intervals in each hour (not sum, since MW is already a rate).
        
        Args:
            records: List of dicts with dispatch_interval, facility_id, quantity
            
        Returns:
            List of hourly aggregated records
        """
        if not records:
            return []
        
        # Group by hour and facility
        hourly_data = defaultdict(lambda: {'total': Decimal('0'), 'count': 0})
        
        for record in records:
            # Round down to hour start (remove minutes, seconds, microseconds)
            hour_start = record['dispatch_interval'].replace(
                minute=0, second=0, microsecond=0
            )
            
            # Create composite key: (hour_start, facility_id)
            key = (hour_start, record['facility_id'])
            
            hourly_data[key]['total'] += record['quantity']
            hourly_data[key]['count'] += 1
        
        # Calculate averages and format output
        aggregated = []
        incomplete_hours = 0
        
        for (hour_start, facility_id), data in hourly_data.items():
            if data['count'] > 0:
                # Average the MW values (not sum, since MW is already a rate)
                average_quantity = data['total'] / data['count']
                
                aggregated.append({
                    'dispatch_interval': hour_start,
                    'facility_id': facility_id,
                    'quantity': average_quantity
                })
                
                # Log warning if we don't have complete hour (12 x 5-min intervals)
                if data['count'] != 12:
                    incomplete_hours += 1
        
        logger.debug(
            f"Aggregated {len(records)} 5-minute records into {len(aggregated)} hourly records"
        )
        
        if incomplete_hours > 0:
            logger.warning(
                f"{incomplete_hours} hours have incomplete data (expected 12 samples/hour)"
            )
        
        return aggregated
    
    @transaction.atomic
    def _save_data(self, records):
        """
        Aggregate to hourly intervals and bulk upsert optimized for MariaDB
        
        Args:
            records: List of 5-minute interval records
            
        Returns:
            Number of hourly records saved
        """
        if not records:
            return 0
        
        # Aggregate 5-minute data to hourly averages
        hourly_records = self._aggregate_to_hourly(records)
        
        if not hourly_records:
            return 0
        
        sql = """
            INSERT INTO facility_scada 
                (dispatch_interval, idfacilities, quantity, created_at)
            VALUES 
                (%s, %s, %s, NOW())
            ON DUPLICATE KEY UPDATE
                quantity = VALUES(quantity)
        """
        
        values = [
            (r['dispatch_interval'], r['facility_id'], r['quantity'])
            for r in hourly_records
        ]
        
        batch_size = 1000
        total_saved = 0
        
        with connection.cursor() as cursor:
            for i in range(0, len(values), batch_size):
                batch = values[i:i + batch_size]
                cursor.executemany(sql, batch)
                total_saved += len(batch)
        
        logger.debug(f"Saved {total_saved} hourly records")
        return total_saved
    
    def verify_data_exists(self, trading_date):
        """
        Check if hourly data exists for a given trading date.
        
        Returns True if we have at least 20 unique hourly intervals
        (allowing for some incomplete data at day boundaries).
        A complete day should have 24 hourly records per facility.
        
        Args:
            trading_date: datetime.date object
            
        Returns:
            Tuple of (exists: bool, count: int)
        """
        start_datetime = datetime.combine(trading_date, datetime.min.time())
        # Make timezone aware
        start_datetime = self.AWST.localize(start_datetime)
        end_datetime = start_datetime + timedelta(days=1)
        
        # Get total count of records
        count = FacilityScada.objects.filter(
            dispatch_interval__gte=start_datetime,
            dispatch_interval__lt=end_datetime
        ).count()
        
        # Count unique hourly intervals
        from django.db.models import Count
        unique_hours = FacilityScada.objects.filter(
            dispatch_interval__gte=start_datetime,
            dispatch_interval__lt=end_datetime
        ).values('dispatch_interval').annotate(
            hour_count=Count('dispatch_interval')
        ).count()
        
        # Data exists if we have at least 20 unique hourly intervals
        # (allowing for some missing data at day boundaries)
        exists = unique_hours >= 20
        
        return exists, count