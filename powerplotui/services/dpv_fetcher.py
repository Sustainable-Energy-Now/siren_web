# powerplot/services/dpv_fetcher.py
import requests
import csv
import io
from datetime import datetime, timedelta
from decimal import Decimal
from django.db import transaction, connection
from django.utils import timezone
import pytz
from siren_web.models import DPVGeneration
import logging

logger = logging.getLogger(__name__)

class DPVDataFetcher:
    """Fetch and store DPV generation estimates from AEMO"""
    
    BASE_URL = "https://data.wa.aemo.com.au/datafiles/distributed-pv/"
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
        
        # Construct filename - AEMO uses format: distributed-pv-YYYY.csv
        filename = f"distributed-pv-{year}.csv"
        url = f"{self.BASE_URL}{filename}"
        
        try:
            logger.info(f"Fetching DPV data from {url}")
            response = self.session.get(url, timeout=60)
            response.raise_for_status()
            
            records = self._parse_csv(response.text, year, month)
            saved_count = self._save_data(records)
            
            logger.info(f"Successfully saved {saved_count} DPV records for {year}-{month:02d}")
            return saved_count
            
        except requests.RequestException as e:
            logger.error(f"Error fetching DPV data from {url}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error processing DPV data: {e}")
            raise
    
    def _parse_csv(self, csv_content, year=None, month=None):
        """Parse CSV content into list of records"""
        records = []
        csv_file = io.StringIO(csv_content)
        reader = csv.DictReader(csv_file)
        
        # Handle different possible header formats
        headers = reader.fieldnames
        
        # Map possible column names (case-insensitive)
        date_col = next((h for h in headers if 'trading date' in h.lower()), None)
        interval_num_col = next((h for h in headers if 'interval number' in h.lower()), None)
        interval_col = next((h for h in headers if 'trading interval' in h.lower()), None)
        generation_col = next((h for h in headers if 'dpv generation' in h.lower() or 'estimated dpv' in h.lower()), None)
        extracted_col = next((h for h in headers if 'extracted' in h.lower()), None)
        
        if not all([date_col, interval_num_col, generation_col]):
            raise ValueError(f"Required columns not found. Headers: {headers}")
        
        logger.info(f"CSV columns mapped - Date: {date_col}, Interval: {interval_num_col}, Generation: {generation_col}")
        
        row_count = 0
        for row in reader:
            try:
                # Parse trading date
                trading_date_str = row[date_col].strip()
                trading_date = self._parse_date(trading_date_str)
                
                # Filter by month if specified (since file contains whole year)
                if month and trading_date.month != month:
                    continue
                
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
                if not generation_str or generation_str == '':
                    continue
                    
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
                
                row_count += 1
                if row_count % 10000 == 0:
                    logger.info(f"Parsed {row_count} rows...")
                
            except (ValueError, KeyError) as e:
                logger.warning(f"Error parsing row: {row}. Error: {e}")
                continue
        
        logger.info(f"Parsed {len(records)} valid DPV records")
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
        """
        Bulk upsert for MariaDB using raw SQL
        Uses INSERT ... ON DUPLICATE KEY UPDATE for maximum performance
        """
        if not records:
            logger.warning("No records to save")
            return 0
        
        # Use raw SQL for MariaDB's efficient bulk upsert
        sql = """
            INSERT INTO dpv_generation 
                (trading_date, interval_number, trading_interval, estimated_generation, extracted_at, created_at)
            VALUES 
                (%s, %s, %s, %s, %s, NOW())
            ON DUPLICATE KEY UPDATE
                estimated_generation = VALUES(estimated_generation),
                extracted_at = VALUES(extracted_at)
        """
        
        values = [
            (
                r['trading_date'],
                r['interval_number'],
                r['trading_interval'],
                r['estimated_generation'],
                r['extracted_at']
            )
            for r in records
        ]
        
        batch_size = 1000
        total_saved = 0
        
        with connection.cursor() as cursor:
            for i in range(0, len(values), batch_size):
                batch = values[i:i + batch_size]
                
                try:
                    cursor.executemany(sql, batch)
                    total_saved += len(batch)
                    
                    if i % 5000 == 0 and i > 0:
                        logger.info(f"Progress: {i}/{len(values)} records saved")
                    
                except Exception as e:
                    logger.error(f"Error executing batch at position {i}: {e}")
                    # Continue with next batch instead of failing completely
                    continue
        
        logger.info(f"MariaDB bulk upsert completed: {total_saved} records processed")
        return total_saved
    
    def fetch_date_range(self, start_date, end_date):
        """Fetch DPV data for a range of months"""
        current_date = start_date.replace(day=1)
        end_date_normalized = end_date.replace(day=1)
        total_saved = 0
        
        while current_date <= end_date_normalized:
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
    
    def fetch_year(self, year):
        """
        Fetch DPV data for an entire year
        Since the file contains all months, this is efficient
        
        Args:
            year: int, year to fetch
        
        Returns:
            int: number of records saved
        """
        filename = f"distributed-pv-{year}.csv"
        url = f"{self.BASE_URL}{filename}"
        
        try:
            logger.info(f"Fetching DPV data for entire year {year} from {url}")
            response = self.session.get(url, timeout=120)
            response.raise_for_status()
            
            # Parse entire year (no month filter)
            records = self._parse_csv(response.text, year=year, month=None)
            saved_count = self._save_data(records)
            
            logger.info(f"Successfully saved {saved_count} DPV records for year {year}")
            return saved_count
            
        except requests.RequestException as e:
            logger.error(f"Error fetching DPV data from {url}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error processing DPV data: {e}")
            raise
    
    def verify_data_exists(self, trading_date):
        """Check if DPV data exists for a given trading date"""
        count = DPVGeneration.objects.filter(trading_date=trading_date).count()
        return count > 0, count