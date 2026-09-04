# powerplot/services/dpv_fetcher.py
import requests
import csv
import io
from collections import defaultdict
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
    
    BASE_URL = "https://data.wa.aemo.com.au/datafiles/estimated-dpv-csv/"
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
        
        # Construct filename - AEMO uses format: distributed-pv-new-YYYY.csv
        filename = f"distributed-pv-new-{year}.csv"
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

        headers = reader.fieldnames or []

        # Current AEMO format: 'Timestamp', 'Estimated DPV Generation(MW)'
        timestamp_col = next((h for h in headers if 'timestamp' in h.lower()), None)
        generation_col = next(
            (h for h in headers if 'dpv generation' in h.lower() or 'estimated dpv' in h.lower()),
            None,
        )

        # Legacy format columns (kept for backward compatibility with old files)
        date_col = next((h for h in headers if 'trading date' in h.lower()), None)
        interval_num_col = next((h for h in headers if 'interval number' in h.lower()), None)
        interval_col = next((h for h in headers if 'trading interval' in h.lower()), None)
        extracted_col = next((h for h in headers if 'extracted' in h.lower()), None)

        if generation_col is None:
            raise ValueError(f"Generation column not found. Headers: {headers}")

        new_format = timestamp_col is not None and date_col is None

        if new_format:
            logger.info(
                f"CSV columns mapped (new format) - Timestamp: {timestamp_col}, "
                f"Generation: {generation_col}"
            )
        else:
            if not all([date_col, interval_num_col]):
                raise ValueError(f"Required columns not found. Headers: {headers}")
            logger.info(
                f"CSV columns mapped (legacy format) - Date: {date_col}, "
                f"Interval: {interval_num_col}, Generation: {generation_col}"
            )

        row_count = 0
        for row in reader:
            try:
                if new_format:
                    timestamp_str = (row.get(timestamp_col) or '').strip()
                    if not timestamp_str:
                        continue

                    # 'Trading Interval' is the timestamp itself; 'Trading Date' and
                    # 'Interval Number' are derived from it (they are no longer supplied).
                    trading_interval = self._parse_datetime(timestamp_str)
                    trading_date, interval_number = self._derive_interval(trading_interval)
                else:
                    trading_date_str = row[date_col].strip()
                    trading_date = self._parse_date(trading_date_str)

                    interval_number = int(row[interval_num_col].strip())

                    if interval_col and row.get(interval_col):
                        trading_interval = self._parse_datetime(row[interval_col].strip())
                    else:
                        # Pre-reform: 48 intervals (30-min), Post-reform: 288 (5-min)
                        step = 5 if trading_date >= datetime(2023, 10, 1).date() else 30
                        minutes = (interval_number - 1) * step
                        trading_interval = datetime.combine(
                            trading_date, datetime.min.time()
                        ) + timedelta(minutes=minutes)
                        trading_interval = self.AWST.localize(trading_interval)

                # Filter by month if specified (file contains whole year)
                if month and trading_date.month != month:
                    continue

                generation_str = (row.get(generation_col) or '').strip()
                if not generation_str:
                    continue

                estimated_generation = Decimal(generation_str)

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

    def _derive_interval(self, trading_interval):
        """
        Derive (trading_date, interval_number) from a trading interval datetime.

        AEMO no longer supplies the 'Trading Date' and 'Interval Number' columns,
        so they are reconstructed from the timestamp. Interval numbering is
        midnight-based (interval 1 == 00:00) to stay consistent with data already
        stored from the legacy file format.
        Pre-reform (before 2023-10-01): 48 x 30-min intervals.
        Post-reform: 288 x 5-min intervals.
        """
        trading_date = trading_interval.date()
        step = 5 if trading_date >= datetime(2023, 10, 1).date() else 30
        minutes_since_midnight = trading_interval.hour * 60 + trading_interval.minute
        interval_number = (minutes_since_midnight // step) + 1
        return trading_date, interval_number

    def _aggregate_to_half_hourly(self, records):
        """
        Consolidate sub-half-hourly DPV estimates into 30-minute intervals.

        AEMO's 'estimated-dpv-csv' files report estimated generation every
        5 minutes. The dpv_generation table and every downstream consumer
        (update_ret_dashboard, ret_dashboard_views, load_analyzer, ...)
        expect one row per 30-minute trading interval, with
        estimated_generation being the average MW over that half hour
        (energy = MW * 0.5h). We therefore average the 5-minute readings
        that fall within each half hour.

        Records already at 30-minute resolution (legacy file format /
        pre-2023-10-01 data) form single-member groups and pass through
        unchanged. interval_number is midnight-based (interval 1 ==
        00:00-00:30) to match rows already stored from the legacy format.

        Args:
            records: list of dicts with trading_date, interval_number,
                trading_interval, estimated_generation, extracted_at

        Returns:
            list of half-hourly aggregated records
        """
        if not records:
            return []

        groups = defaultdict(list)
        for r in records:
            ti = r['trading_interval']
            hh_index = (ti.hour * 60 + ti.minute) // 30  # 0..47
            groups[(r['trading_date'], hh_index)].append(r)

        aggregated = []
        unexpected = 0
        for (trading_date, hh_index), group in groups.items():
            half_hour_start = group[0]['trading_interval'].replace(
                hour=(hh_index * 30) // 60,
                minute=(hh_index * 30) % 60,
                second=0,
                microsecond=0,
            )
            avg_mw = sum(g['estimated_generation'] for g in group) / len(group)

            aggregated.append({
                'trading_date': trading_date,
                'interval_number': hh_index + 1,
                'trading_interval': half_hour_start,
                'estimated_generation': avg_mw,
                'extracted_at': max(g['extracted_at'] for g in group),
            })

            if len(group) not in (1, 6):
                unexpected += 1

        if unexpected:
            logger.warning(
                f"{unexpected} half-hour interval(s) had an unexpected reading "
                "count (expected 6 five-minute readings, or 1 for legacy "
                "30-minute data)"
            )

        aggregated.sort(key=lambda r: (r['trading_date'], r['interval_number']))
        logger.info(
            f"Consolidated {len(records)} readings into {len(aggregated)} "
            "half-hourly DPV records"
        )
        return aggregated

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
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%d %H:%M',
            '%Y-%m-%dT%H:%M',
            '%d/%m/%Y %H:%M:%S',
            '%d/%m/%Y %H:%M',
            '%d-%m-%Y %H:%M:%S',
            '%d-%m-%Y %H:%M',
            '%Y/%m/%d %H:%M:%S',
            '%Y/%m/%d %H:%M',
        ]

        cleaned = datetime_str.strip()
        # Drop any timezone suffix / fractional seconds AEMO may add
        if cleaned.endswith('Z'):
            cleaned = cleaned[:-1]
        if '.' in cleaned:
            cleaned = cleaned.split('.', 1)[0]

        for fmt in datetime_formats:
            try:
                dt = datetime.strptime(cleaned, fmt)
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

        # AEMO now supplies 5-minute data; collapse it to the half-hourly
        # resolution the dpv_generation table and its consumers expect.
        records = self._aggregate_to_half_hourly(records)
        if not records:
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
        filename = f"distributed-pv-new-{year}.csv"
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