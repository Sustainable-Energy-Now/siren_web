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
from siren_web.models import FacilityScada, DailyPeakRE, facilities, Technologies
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
                    # Backfill DailyPeakRE if missing
                    if not DailyPeakRE.objects.filter(trading_date=current_date).exists():
                        peak = self._calculate_half_hourly_peak_re(current_date)
                        if peak:
                            DailyPeakRE.objects.create(
                                trading_date=current_date,
                                peak_re_percentage=peak['percentage'],
                                peak_re_datetime=peak['datetime'],
                                re_generation_mw=peak['re_mw'],
                                total_generation_mw=peak['total_mw'],
                            )
                            logger.info(f"  Backfilled DailyPeakRE: {peak['percentage']:.1f}%")
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
                    # Backfill DailyPeakRE if missing
                    if not DailyPeakRE.objects.filter(trading_date=current_date).exists():
                        peak = self._calculate_half_hourly_peak_re(current_date)
                        if peak:
                            DailyPeakRE.objects.create(
                                trading_date=current_date,
                                peak_re_percentage=peak['percentage'],
                                peak_re_datetime=peak['datetime'],
                                re_generation_mw=peak['re_mw'],
                                total_generation_mw=peak['total_mw'],
                            )
                            logger.info(f"  Backfilled DailyPeakRE: {peak['percentage']:.1f}%")
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
    
    def _aggregate_to_half_hourly(self, records):
        """
        Aggregate 5-minute dispatch intervals into half-hourly energy totals.

        Quantity is in mWh at 5-minute resolution, so for each half-hour we SUM
        the 6 intervals to obtain half-hourly mWh.

        Args:
            records: List of dicts with dispatch_interval, facility_id, quantity

        Returns:
            List of half-hourly aggregated records
        """
        if not records:
            return []

        from collections import defaultdict
        half_hourly_data = defaultdict(lambda: {'total': Decimal('0'), 'count': 0})

        # Group by (half_hour_start, facility_id)
        for record in records:
            dt = record['dispatch_interval']
            half_hour_start = dt.replace(
                minute=(dt.minute // 30) * 30, second=0, microsecond=0
            )
            key = (half_hour_start, record['facility_id'])

            half_hourly_data[key]['total'] += record['quantity']
            half_hourly_data[key]['count'] += 1

        aggregated = []
        incomplete_intervals = 0

        for (half_hour_start, facility_id), data in half_hourly_data.items():
            total_quantity = data['total']   # SUM of mWh values

            aggregated.append({
                'dispatch_interval': half_hour_start,
                'facility_id': facility_id,
                'quantity': total_quantity
            })

            if data['count'] != 6:
                incomplete_intervals += 1

        if incomplete_intervals > 0:
            logger.warning(
                f"{incomplete_intervals} half-hours have incomplete data "
                "(expected 6 samples per half-hour)"
            )

        logger.debug(
            f"Aggregated {len(records)} 5-minute records into {len(aggregated)} half-hourly records"
        )

        return aggregated

    def _calculate_daily_peak_re(self, records):
        """
        Calculate peak 5-minute instantaneous operational RE% from raw records.

        RE sources: fuel_type in (WIND, SOLAR, BIOMASS, HYDRO) or category = Storage.
        Must match the re_condition in update_ret_dashboard.calculate_best_re_hour().

        Args:
            records: List of 5-min dicts with dispatch_interval, facility_id, quantity

        Returns:
            dict keyed by date with peak RE% data
        """
        # Build facility_id -> is_re lookup
        facility_ids = {r['facility_id'] for r in records}
        re_facility_ids = set()

        facility_qs = facilities.objects.filter(
            idfacilities__in=facility_ids
        ).select_related('idtechnologies')

        for f in facility_qs:
            tech = f.idtechnologies
            if tech:
                fuel_type = (tech.fuel_type or '').upper()
                category = (tech.category or '').upper()
                if fuel_type in ('WIND', 'SOLAR', 'BIOMASS', 'HYDRO') or category == 'STORAGE':
                    re_facility_ids.add(f.idfacilities)

        # Group records by dispatch_interval, sum RE and total generation
        interval_totals = defaultdict(lambda: {'re_mw': 0.0, 'total_mw': 0.0})

        for record in records:
            qty = float(record['quantity'])
            if qty <= 0:
                continue

            dt = record['dispatch_interval']
            interval_totals[dt]['total_mw'] += qty

            if record['facility_id'] in re_facility_ids:
                interval_totals[dt]['re_mw'] += qty

        # Find daily peaks
        daily_peaks = {}
        for dt, totals in interval_totals.items():
            if totals['total_mw'] <= 0:
                continue
            re_pct = (totals['re_mw'] / totals['total_mw']) * 100
            day = dt.date() if hasattr(dt, 'date') else dt

            if day not in daily_peaks or re_pct > daily_peaks[day]['percentage']:
                daily_peaks[day] = {
                    'percentage': re_pct,
                    'datetime': dt,
                    're_mw': totals['re_mw'],
                    'total_mw': totals['total_mw'],
                }

        return daily_peaks

    def _store_daily_peak_re(self, daily_peaks):
        """Store daily peak RE% records in DailyPeakRE table."""
        for day, peak in daily_peaks.items():
            DailyPeakRE.objects.update_or_create(
                trading_date=day,
                defaults={
                    'peak_re_percentage': peak['percentage'],
                    'peak_re_datetime': peak['datetime'],
                    're_generation_mw': peak['re_mw'],
                    'total_generation_mw': peak['total_mw'],
                }
            )
            logger.info(
                f"Daily peak RE% for {day}: {peak['percentage']:.1f}% "
                f"at {peak['datetime']}"
            )

    def _calculate_half_hourly_peak_re(self, trading_date):
        """
        Calculate peak half-hourly RE% from existing FacilityScada records.
        Used as fallback when 5-minute data is not available.

        Args:
            trading_date: datetime.date object

        Returns:
            dict with percentage, datetime, re_mw, total_mw or None
        """
        from django.db.models import Sum, Case, When, Value, DecimalField, F, Q

        start_dt = self.AWST.localize(datetime.combine(trading_date, datetime.min.time()))
        end_dt = start_dt + timedelta(days=1)

        scada_qs = FacilityScada.objects.filter(
            dispatch_interval__gte=start_dt,
            dispatch_interval__lt=end_dt,
            quantity__gt=0,
        )

        if not scada_qs.exists():
            return None

        re_condition = (
            Q(facility__idtechnologies__fuel_type__in=['WIND', 'SOLAR', 'BIOMASS', 'HYDRO']) |
            Q(facility__idtechnologies__category__iexact='storage')
        )

        interval_stats = scada_qs.values('dispatch_interval').annotate(
            re_gen=Sum(
                Case(
                    When(re_condition, then=F('quantity')),
                    default=Value(0),
                    output_field=DecimalField(),
                )
            ),
            total_gen=Sum('quantity'),
        )

        best = None
        for interval in interval_stats:
            total = float(interval['total_gen'] or 0)
            re = float(interval['re_gen'] or 0)
            if total > 0:
                pct = (re / total) * 100
                if best is None or pct > best['percentage']:
                    best = {
                        'percentage': pct,
                        'datetime': interval['dispatch_interval'],
                        're_mw': re,
                        'total_mw': total,
                    }

        return best

    def backfill_daily_peak_re(self, start_date, end_date):
        """
        Backfill DailyPeakRE records from existing half-hourly FacilityScada data
        for days that have SCADA data but no DailyPeakRE record.

        Args:
            start_date: datetime.date
            end_date: datetime.date

        Returns:
            dict with backfilled and skipped counts
        """
        current_date = start_date
        backfilled = 0
        skipped = 0

        while current_date <= end_date:
            if not DailyPeakRE.objects.filter(trading_date=current_date).exists():
                peak = self._calculate_half_hourly_peak_re(current_date)
                if peak:
                    DailyPeakRE.objects.create(
                        trading_date=current_date,
                        peak_re_percentage=peak['percentage'],
                        peak_re_datetime=peak['datetime'],
                        re_generation_mw=peak['re_mw'],
                        total_generation_mw=peak['total_mw'],
                    )
                    logger.info(
                        f"Backfilled DailyPeakRE for {current_date}: "
                        f"{peak['percentage']:.1f}%"
                    )
                    backfilled += 1
                else:
                    skipped += 1
            else:
                skipped += 1

            current_date += timedelta(days=1)

        return {'backfilled': backfilled, 'skipped': skipped}

    @transaction.atomic
    def _save_data(self, records):
        """
        Aggregate to half-hourly intervals and bulk upsert optimized for MariaDB

        Args:
            records: List of 5-minute interval records

        Returns:
            Number of half-hourly records saved
        """
        if not records:
            return 0

        # Calculate 5-minute peak RE% BEFORE aggregation discards the data
        try:
            daily_peaks = self._calculate_daily_peak_re(records)
            self._store_daily_peak_re(daily_peaks)
        except Exception as e:
            logger.warning(f"Error calculating daily peak RE%: {e}")

        # Aggregate 5-minute data to half-hourly totals
        hourly_records = self._aggregate_to_half_hourly(records)

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
        
        logger.debug(f"Saved {total_saved} half-hourly records")
        return total_saved
    
    def verify_data_exists(self, trading_date):
        """
        Check if half-hourly data exists for a given trading date.

        Returns True if we have at least 40 unique half-hourly intervals
        (allowing for some incomplete data at day boundaries).
        A complete day should have 48 half-hourly records per facility.

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

        # Count unique half-hourly intervals
        from django.db.models import Count
        unique_intervals = FacilityScada.objects.filter(
            dispatch_interval__gte=start_datetime,
            dispatch_interval__lt=end_datetime
        ).values('dispatch_interval').annotate(
            interval_count=Count('dispatch_interval')
        ).count()

        # Data exists if we have at least 40 unique half-hourly intervals
        # (allowing for some missing data at day boundaries)
        exists = unique_intervals >= 40

        return exists, count