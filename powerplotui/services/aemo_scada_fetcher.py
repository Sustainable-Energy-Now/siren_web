# powerplot/services/aemo_scada_fetcher.py
import requests
import json
from datetime import datetime, timedelta
from decimal import Decimal
from django.db import transaction, connection
from django.utils import timezone
from django.core.cache import cache
import pytz
from siren_web.models import FacilityScada, facilities
import logging

logger = logging.getLogger(__name__)

class AEMOScadaFetcher:
    BASE_URL = "https://data.wa.aemo.com.au/public/market-data/wemde/facilityScada/current/"
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
        from siren_web.models import Technologies
        
        # Get or create 'Unknown' technology
        unknown_tech, _ = Technologies.objects.get_or_create(
            technology='Unknown',
            defaults={'technology_type': 'Unknown'}
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
        """Fetch SCADA data for a trading day"""
        if trading_date is None:
            trading_date = (timezone.now().astimezone(self.AWST).date() - 
                          timedelta(days=1))
        
        url = f"{self.BASE_URL}SCADA_{trading_date.strftime('%Y-%m-%d')}.json"
        
        try:
            logger.info(f"Fetching SCADA data from {url}")
            response = requests.get(url, timeout=60)
            response.raise_for_status()
            
            data = response.json()
            records = self._parse_data(data)
            saved_count = self._save_data(records)
            
            logger.info(f"Successfully saved {saved_count} SCADA records for {trading_date}")
            return saved_count
            
        except requests.RequestException as e:
            logger.error(f"Error fetching SCADA data from {url}: {e}")
            return self._try_alternative_urls(trading_date)
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing JSON from {url}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise
    
    def _try_alternative_urls(self, trading_date):
        """Try alternative URL patterns"""
        alternative_patterns = [
            f"{self.BASE_URL}SCADA{trading_date.strftime('%Y%m%d')}.json",
            f"{self.BASE_URL}facilityScada-{trading_date.strftime('%Y%m%d')}.json",
            f"{self.BASE_URL}facilityScada-{trading_date.strftime('%Y-%m-%d')}.json",
        ]
        
        for url in alternative_patterns:
            try:
                logger.info(f"Trying alternative URL: {url}")
                response = requests.get(url, timeout=60)
                response.raise_for_status()
                
                data = response.json()
                records = self._parse_data(data)
                saved_count = self._save_data(records)
                
                logger.info(f"Successfully fetched from alternative URL: {saved_count} records")
                return saved_count
            except Exception as e:
                logger.debug(f"Alternative URL failed: {url} - {e}")
                continue
        
        raise Exception(f"Could not fetch SCADA data for {trading_date} from any URL pattern")
    
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
        
        logger.info(f"Parsed {len(records)} records from JSON")
        return records
    
    @transaction.atomic
    def _save_data(self, records):
        """Bulk upsert optimized for MariaDB"""
        if not records:
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
            for r in records
        ]
        
        batch_size = 1000
        total_saved = 0
        
        with connection.cursor() as cursor:
            for i in range(0, len(values), batch_size):
                batch = values[i:i + batch_size]
                cursor.executemany(sql, batch)
                total_saved += len(batch)
                
                if i % 5000 == 0 and i > 0:
                    logger.info(f"Progress: {i}/{len(values)} records")
        
        logger.info(f"Completed: {total_saved} records saved")
        return total_saved
    
    def verify_data_exists(self, trading_date):
        """Check if data exists for a given trading date"""
        start_datetime = datetime.combine(trading_date, datetime.min.time())
        end_datetime = start_datetime + timedelta(days=1)
        
        count = FacilityScada.objects.filter(
            dispatch_interval__gte=start_datetime,
            dispatch_interval__lt=end_datetime
        ).count()
        
        return count > 0, count