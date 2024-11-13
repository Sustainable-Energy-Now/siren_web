# powermatchui/management/commands/load_reference_prices.py
from datetime import datetime
from collections import defaultdict
import json
import zipfile
from io import BytesIO
import requests
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand
from siren_web.models import TradingPrice

class Command(BaseCommand):
    help = 'Updates trading prices from AEMO WEMDE reference trading price JSON files'
    
    base_url = 'https://data.wa.aemo.com.au/public/market-data/wemde/referenceTradingPrice/previous/'
    
    def get_json_filenames(self):
        """
        Fetch list of zipped JSON filenames from the AEMO directory.
        Returns a list of filenames sorted chronologically.
        """
        try:
            response = requests.get(self.base_url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            zip_files = [
                link.get('href').split('/')[-1]
                for link in soup.find_all('a')
                if link.get('href', '').endswith('.zip')
            ]
            
            return sorted(zip_files)
            
        except requests.RequestException as e:
            self.stdout.write(
                self.style.ERROR(f'Error fetching directory listing: {str(e)}')
            )
            return []

    def calculate_monthly_averages(self, json_data):
        """
        Calculate monthly averages from the JSON trading price data.
        Returns a dict with (month, interval) as key and average price as value.
        """
        monthly_prices = defaultdict(lambda: defaultdict(list))
        
        try:
            # Extract the trading day and prices from the nested structure
            trading_day = json_data['data']['tradingDay']
            reference_prices = json_data['data']['referenceTradingPrices']
            
            # Process each price entry
            for entry in reference_prices:
                try:
                    # Create datetime from trading day and interval
                    trading_date = datetime.strptime(trading_day, "%Y-%m-%d")
                    month_key = trading_date.strftime("%Y-%m")
                    
                    # Parse the trading interval to get the interval number
                    interval_datetime = datetime.strptime(entry['tradingInterval'], "%Y-%m-%dT%H:%M:%S%z")
                    # Calculate interval number (1-48 instead of 0-47)
                    interval = (interval_datetime.hour * 2) + (interval_datetime.minute // 30) + 1
                    
                    price = float(entry['referenceTradingPrice'])
                    
                    monthly_prices[month_key][interval].append(price)
                    
                except (ValueError, KeyError) as e:
                    self.stdout.write(
                        self.style.WARNING(f'Skipping price entry due to data error: {str(e)}')
                    )
                    continue
                    
        except KeyError as e:
            self.stdout.write(
                self.style.WARNING(f'Error accessing JSON structure: {str(e)}')
            )
            return {}
        
        # Calculate averages for each month and interval
        monthly_averages = {}
        for month, intervals in monthly_prices.items():
            for interval, prices in intervals.items():
                if prices:  # Check if we have prices for this interval
                    avg_price = sum(prices) / len(prices)
                    monthly_averages[(month, interval)] = avg_price
        
        return monthly_averages

    def process_zip_file(self, filename):
        """
        Process a single zipped JSON file and return the number of records created/updated.
        """
        file_url = self.base_url + filename
        try:
            # Download the zip file
            response = requests.get(file_url)
            response.raise_for_status()
            
            # Create a BytesIO object from the response content
            zip_buffer = BytesIO(response.content)
            
            # Open the zip file
            with zipfile.ZipFile(zip_buffer) as zip_file:
                # Get the first JSON file in the archive
                json_filename = [
                    f for f in zip_file.namelist() 
                    if f.endswith('.json')
                ][0]
                
                # Read and parse the JSON data
                with zip_file.open(json_filename) as json_file:
                    json_data = json.load(json_file)
                    
                    # Check for errors in the response
                    if json_data.get('errors'):
                        self.stdout.write(
                            self.style.WARNING(f'File contains errors: {json_data["errors"]}')
                        )
                    
                    # Calculate monthly averages
                    monthly_averages = self.calculate_monthly_averages(json_data)
                    
                    if not monthly_averages:
                        self.stdout.write(
                            self.style.WARNING(f'No valid price data found in {filename}')
                        )
                        return 0
                    
                    # Counter for created/updated records
                    record_count = 0
                    
                    # Create or update TradingPrice records
                    for (month_str, interval), avg_price in monthly_averages.items():
                        trading_month = datetime.strptime(month_str, "%Y-%m")
                        
                        # Update or create the trading price record
                        _, created = TradingPrice.objects.update_or_create(
                            trading_month=trading_month,
                            trading_interval=interval,
                            defaults={'reference_price': avg_price}
                        )
                        
                        record_count += 1
                    
                    return record_count
            
        except requests.RequestException as e:
            self.stdout.write(
                self.style.ERROR(f'Error downloading {filename}: {str(e)}')
            )
            return 0
        except zipfile.BadZipFile as e:
            self.stdout.write(
                self.style.ERROR(f'Error extracting {filename}: {str(e)}')
            )
            return 0
        except json.JSONDecodeError as e:
            self.stdout.write(
                self.style.ERROR(f'Error parsing JSON from {filename}: {str(e)}')
            )
            return 0
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Unexpected error processing {filename}: {str(e)}')
            )
            return 0

    def handle(self, *args, **kwargs):
        self.stdout.write('Fetching list of Zipped files...')
        zip_files = self.get_json_filenames()
        
        if not zip_files:
            self.stdout.write(
                self.style.ERROR('No zip files found in directory')
            )
            return
        
        total_records = 0
        total_files = len(zip_files)
        
        self.stdout.write(f'Found {total_files} ZIP files to process')
        
        # Process each JZIP file
        for index, filename in enumerate(zip_files, 1):
            self.stdout.write(f'Processing file {index}/{total_files}: {filename}')
            records = self.process_zip_file(filename)
            total_records += records
            self.stdout.write(
                self.style.SUCCESS(f'Processed {records} records from {filename}')
            )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully processed all files. Total records created/updated: {total_records}'
            )
        )
