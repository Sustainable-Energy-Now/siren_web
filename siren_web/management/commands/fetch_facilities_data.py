import requests
from django.core.management.base import BaseCommand
from siren_web.models import TradingPrice
from datetime import datetime

class Command(BaseCommand):
    help = 'Fetch trading price data every 30 minutes'

    def handle(self, *args, **kwargs):
        # url = 'https://data.wa.aemo.com.au/public/market-data/wemde/referenceTradingPrice/current'
        # 'https://data.wa.aemo.com.au/public/public-data/datafiles/facility-scada/'
        # 'https://data.wa.aemo.com.au/public/public-data/datafiles/facility-temperature/'
        # 'https://data.wa.aemo.com.au/public/public-data/datafiles/symphony/'
        # 'https://data.wa.aemo.com.au/public/public-data/datafiles/load-forecast/'
        # 'https://data.wa.aemo.com.au/public/public-data/datafiles/load-summary/'
        # 'https://data.wa.aemo.com.au/public/public-data/datafiles/ncs-dispatch-information/'
        # 'https://data.wa.aemo.com.au/public/public-data/datafiles/operational-demand/'
        url = 'https://data.wa.aemo.com.au/public/public-data/datafiles/facilities/'
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            prices = data['data']['referenceTradingPrices']

            for entry in prices:
                trading_interval = datetime.fromisoformat(entry['tradingInterval'])
                price = entry['referenceTradingPrice']
                published = entry['isPublished']

                # Check if the entry already exists
                TradingPrice.objects.update_or_create(
                    trading_interval=trading_interval,
                    defaults={'reference_price': price, 'is_published': published}
                )

            self.stdout.write(self.style.SUCCESS('Successfully updated trading prices'))
        else:
            self.stdout.write(self.style.ERROR('Failed to fetch data'))
