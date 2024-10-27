# powermatchui/management/commands/load_TradePrices.py
from decimal import Decimal
import os
import csv
from datetime import datetime
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from siren_web.models import TradingPrice

class Command(BaseCommand):
    help = 'Load trading prices from a CSV file'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Path to the CSV file')

    def handle(self, *args, **kwargs):
        csv_file_path = kwargs['csv_file']
        with open(csv_file_path, 'r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                naive_datetime = datetime.strptime(row['Trading Interval'], "%Y-%m-%d %H:%M:%S")
                aware_datetime = timezone.make_aware(naive_datetime, timezone.get_current_timezone())
                TradingPrice.objects.create(
                    trading_interval=aware_datetime,
                    reference_price=float(row['Final Price ($/MWh)'])
                )
        self.stdout.write(self.style.SUCCESS('TradePrices loaded successfully'))