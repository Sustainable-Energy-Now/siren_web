# powerplot/services/dpv_fetcher.py
import requests
import csv
import io
from datetime import datetime, timedelta
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
import pytz
from siren_web.models import DPVGeneration
import logging

logger = logging.getLogger(__name__)

class DPVDataFetcher:
    """Fetch and store DPV generation estimates from AEMO"""
    
    BASE_URL = "https://aemo.com.au/aemo/data/wa/infographic/generation-mix/"
    AWST = pytz.timezone('Australia/Perth')
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def fetch_dpv_data(self, year=None, month=None):
        """
        Fetch DPV generation data for a specific month
        
        Args:
            year: int, year to fetch (defaults to current year)
            month: int, month to fetch (defaults to current month)
        
        Returns:
            int: number of records saved
        """
        if year is None or month is None:
            now = timezone.now().astimezone(self.AWST)
            year = year or now.year
            month = month or now.month
        
        # Construct filename - AEMO typically uses format like: dpv-estimates-YYYYMM.csv
        filename = f"estimated-dpv-{year}{month:02d}.csv"
        url = f"{self.BASE_URL}{filename}"
        
        try:
            logger.info(f"Fetching DPV data from {url}")
            response = self.session.get(url, timeout=60)
            response.raise_for_status()
            
            records = self._parse_csv(response.text)
            saved_count = self._save_data(records)
            
            logger.info(f"Successfully saved {saved_count} DPV records for {year}-{month:02d}")
            return saved_count
            
        except requests.RequestException as e:
            logger.error(f"Error fetching DPV data from {url}: {e}")
            # Try alternative URL pattern
            return self._try_alternative_url(year, month)
        except Exception as e:
            logger.error(f"Error processing DPV data: {e}")
            raise
    
    def _try_alternative_url(self, year, month):
        """Try alternative URL patterns for DPV data"""
        alternative_patterns = [
            f"https://data.wa.aemo.com.au/public/public-data/datafiles/facility-scada/estimated-dpv/estimated-dpv-{year}{month:02d}.csv",
            f"https://aemo.com.au/-/media/files/electricity/wem/data/estimated-dpv-{year}-{month:02d}.csv",
        ]
        
        for url in alternative_patterns:
            try:
                logger.info(f"Trying alternative URL: {url}")
                response = self.session.get(url, timeout=60)
                response.raise_for_status()
                
                records = self._parse_csv(response.text)
                saved_count = self._save_data(records)
                
                logger.info(f"Successfully fetched from alternative URL: {saved_count} records")
                return saved_count
            except Exception as e:
                logger.warning(f"Alternative URL failed: {url} - {e}")
                continue
        
        raise Exception(f"Could not fetch DPV data for {year}-{month:02d} from any URL")
    
    def _parse_csv(self, csv_content):
        """Parse CSV content into list of records"""
        records = []
        csv_file = io.StringIO(csv_content)
        reader = csv.DictReader(csv_file)
        
        # Handle different possible header formats
        headers = reader.fieldnames
        
        # Map possible column names
        date_col = next((h for h in headers if 'trading date' in h.lower()), None)
        interval_num_col = next((h for h in headers if 'interval number' in h.lower()), None)
        interval_col = next((h for h in headers if 'trading interval' in h.lower()), None)
        generation_col = next((h for h in headers if 'dpv generation' in h.lower()), None)
        extracted_col = next((h for h in headers if 'extracted' in h.lower()), None)
        
        if not all([date_col, interval_num_col, generation_col]):
            raise ValueError(f"Required columns not found. Headers: {headers}")
        
        for row in reader:
            try:
                # Parse trading date
                trading_date_str = row[date_col].strip()
                trading_date = self._parse_date(trading_date_str)
                
                # Parse interval number
                interval_number = int(row[interval_num_col].strip())
                
                # Parse trading interval
                if interval_col and row.get(interval_col):
                    trading_interval = self._parse_datetime(row[interval_col].strip())
                else:
                    # Calculate from trading_date and interval_number
                    # Pre-reform: 48 intervals (30-min), Post-reform: 288 intervals (5-min)
                    if trading_date >= datetime(2023, 10, 1).date():
                        # 5-minute intervals
                        minutes = (interval_number - 1) * 5
                    else:
                        # 30-minute intervals
                        minutes = (interval_number - 1) * 30
                    
                    trading_interval = datetime.combine(
                        trading_date,
                        datetime.min.time()
                    ) + timedelta(minutes=minutes)
                    trading_interval = self.AWST.localize(trading_interval)
                
                # Parse generation value
                generation_str = row[generation_col].strip()
                estimated_generation = Decimal(generation_str)
                
                # Parse extracted_at
                if extracted_col and row.get(extracted_col):
                    extracted_at = self._parse_datetime(row[extracted_col].strip())
                else:
                    extracted_at = timezone.now()
                
                records.append({
                    'trading_date': trading_date,
                    'interval_number': interval_number,
                    'trading_interval': trading_interval,
                    'estimated_generation': estimated_generation,
                    'extracted_at': extracted_at
                })
                
            except (ValueError, KeyError) as e:
                logger.warning(f"Error parsing row: {row}. Error: {e}")
                continue
        
        return records
    
    def _parse_date(self, date_str):
        """Parse date string in various formats"""
        date_formats = ['%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%Y/%m/%d']
        
        for fmt in date_formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        
        raise ValueError(f"Could not parse date: {date_str}")
    
    def _parse_datetime(self, datetime_str):
        """Parse datetime string in various formats"""
        datetime_formats = [
            '%d/%m/%Y %H:%M',
            '%Y-%m-%d %H:%M',
            '%d-%m-%Y %H:%M',
            '%d/%m/%Y %H:%M:%S',
            '%Y-%m-%d %H:%M:%S',
        ]
        
        for fmt in datetime_formats:
            try:
                dt = datetime.strptime(datetime_str, fmt)
                # Localize to AWST if naive
                if dt.tzinfo is None:
                    dt = self.AWST.localize(dt)
                return dt
            except ValueError:
                continue
        
        raise ValueError(f"Could not parse datetime: {datetime_str}")
    
    @transaction.atomic
    def _save_data(self, records):
        """Bulk insert/update DPV records"""
        if not records:
            return 0
        
        objects_to_create = []
        
        for record in records:
            objects_to_create.append(
                DPVGeneration(
                    trading_date=record['trading_date'],
                    interval_number=record['interval_number'],
                    trading_interval=record['trading_interval'],
                    estimated_generation=record['estimated_generation'],
                    extracted_at=record['extracted_at']
                )
            )
        
        # Use bulk_create with update on conflict (PostgreSQL)
        try:
            DPVGeneration.objects.bulk_create(
                objects_to_create,
                update_conflicts=True,
                update_fields=['estimated_generation', 'extracted_at'],
                unique_fields=['trading_date', 'interval_number']
            )
        except Exception as e:
            # Fallback for databases that don't support bulk_create with conflicts
            logger.warning(f"Bulk create with conflicts failed, using update_or_create: {e}")
            for obj in objects_to_create:
                DPVGeneration.objects.update_or_create(
                    trading_date=obj.trading_date,
                    interval_number=obj.interval_number,
                    defaults={
                        'trading_interval': obj.trading_interval,
                        'estimated_generation': obj.estimated_generation,
                        'extracted_at': obj.extracted_at
                    }
                )
        
        return len(objects_to_create)
    
    def fetch_date_range(self, start_date, end_date):
        """Fetch DPV data for a range of months"""
        current_date = start_date.replace(day=1)
        end_date = end_date.replace(day=1)
        total_saved = 0
        
        while current_date <= end_date:
            try:
                count = self.fetch_dpv_data(current_date.year, current_date.month)
                total_saved += count
                logger.info(f"Fetched {count} records for {current_date.year}-{current_date.month:02d}")
            except Exception as e:
                logger.error(f"Failed to fetch DPV for {current_date.year}-{current_date.month:02d}: {e}")
            
            # Move to next month
            if current_date.month == 12:
                current_date = current_date.replace(year=current_date.year + 1, month=1)
            else:
                current_date = current_date.replace(month=current_date.month + 1)
        
        return total_saved