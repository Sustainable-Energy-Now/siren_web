# powermatchui/management/commands/load_TradePrices.py
from decimal import Decimal
import csv
from datetime import datetime
from collections import defaultdict
from django.core.management.base import BaseCommand
from django.utils import timezone
import requests
from bs4 import BeautifulSoup
from siren_web.models import TradingPrice

class Command(BaseCommand):
    help = 'Updates trading prices from the AEMO data repository csv files with monthly averages'
    
    base_url = 'https://data.wa.aemo.com.au/datafiles/balancing-summary/'
    def get_csv_filenames(self):
        """
        Fetch list of CSV filenames from the AEMO directory.
        Returns a list of CSV filenames without the path.
        """
        try:
            response = requests.get(self.base_url)
            response.raise_for_status()
            
            # Parse the directory listing
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find all links that end in .csv and extract just the filename
            csv_files = []
            for link in soup.find_all('a'):
                href = link.get('href')
                if href and href.endswith('.csv'):
                    # Get just the filename without the path
                    filename = href.split('/')[-1]
                    csv_files.append(filename)
            
            return sorted(csv_files)  # Sort to process in chronological order
            
        except requests.RequestException as e:
            self.stdout.write(
                self.style.ERROR(f'Error fetching directory listing: {str(e)}')
            )
            return []
        
    def calculate_monthly_averages(self, csv_reader):
        """
        Calculate monthly averages for each trading interval from the CSV data.
        Returns a dict with (month, interval) as key and average price as value.
        """
        # Use nested defaultdict to accumulate prices for each month and interval
        monthly_prices = defaultdict(lambda: defaultdict(list))
        
        for row in csv_reader:
            try:
                month_key = row['Trading Date'][0:7]
                interval = int(row['Interval Number'])
                price = float(row['Final Price ($/MWh)'])
                
                monthly_prices[month_key][interval].append(price)
            except (ValueError, KeyError) as e:
                self.stdout.write(
                    self.style.WARNING(f'Skipping row due to data error: {str(e)}')
                )
                continue
        
        # Calculate averages
        monthly_averages = {}
        for month, intervals in monthly_prices.items():
            for interval, prices in intervals.items():
                if prices:  # Check if we have prices for this interval
                    avg_price = sum(prices) / len(prices)
                    monthly_averages[(month, interval)] = avg_price
        
        return monthly_averages

    def process_csv_file(self, full_url):
        """
        Process a single CSV file and return the number of records created/updated.
        """
        try:
            response = requests.get(full_url)
            response.raise_for_status()
            
            # Decode the content and create a CSV reader
            csv_content = response.content.decode('utf-8').splitlines()
            csv_reader = csv.DictReader(csv_content)
            
            # Calculate monthly averages for this file
            monthly_averages = self.calculate_monthly_averages(csv_reader)
            
            # Counter for created/updated records
            record_count = 0
            
            # Create or update TradingPrice records
            for (month_str, interval), avg_price in monthly_averages.items():
                trading_month = datetime.strptime(month_str, "%Y-%m")
                
                TradingPrice.objects.create(
                    trading_month=trading_month,
                    trading_interval=interval,
                    reference_price=avg_price
                )    
                record_count += 1
            
            return record_count
            
        except requests.RequestException as e:
            self.stdout.write(
                self.style.ERROR(f'Error processing {full_url}: {str(e)}')
            )
            return 0
        except csv.Error as e:
            self.stdout.write(
                self.style.ERROR(f'Error parsing {full_url}: {str(e)}')
            )
            return 0
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Unexpected error processing {full_url}: {str(e)}')
            )
            return 0

    def handle(self, *args, **kwargs):
        self.stdout.write('Fetching list of CSV files...')
        csv_files = self.get_csv_filenames()
        
        if not csv_files:
            self.stdout.write(
                self.style.ERROR('No CSV files found in directory')
            )
            return
        
        total_records = 0
        total_files = len(csv_files)
        
        self.stdout.write(f'Found {total_files} CSV files to process')
        
        # Process each CSV file
        for index, file_url in enumerate(csv_files, 1):
            full_url = self.base_url + file_url
            self.stdout.write(f'Processing file {index}/{total_files}: {full_url}')
            records = self.process_csv_file(full_url)
            total_records += records
            self.stdout.write(
                self.style.SUCCESS(f'Processed {records} records from file')
            )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully processed all files. Total records created/updated: {total_records}'
            )
        )
