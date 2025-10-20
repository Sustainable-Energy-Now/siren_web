# powerplot/management/commands/check_missing_scada_dates.py
from django.core.management.base import BaseCommand
from siren_web.models import FacilityScada
from datetime import datetime, timedelta, date
from django.db.models import Count
from django.db.models.functions import TruncDate

class Command(BaseCommand):
    help = 'Check for missing dates in SCADA data'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--start-date',
            type=str,
            required=True,
            help='Start date (YYYY-MM-DD)',
        )
        parser.add_argument(
            '--end-date',
            type=str,
            required=True,
            help='End date (YYYY-MM-DD)',
        )
    
    def handle(self, *args, **options):
        start_date = datetime.strptime(options['start_date'], '%Y-%m-%d').date()
        end_date = datetime.strptime(options['end_date'], '%Y-%m-%d').date()
        
        # Get dates with data
        dates_with_data = set(
            FacilityScada.objects.filter(
                dispatch_interval__date__gte=start_date,
                dispatch_interval__date__lte=end_date
            ).annotate(
                date=TruncDate('dispatch_interval')
            ).values_list('date', flat=True).distinct()
        )
        
        # Generate expected dates
        current = start_date
        expected_dates = set()
        while current <= end_date:
            expected_dates.add(current)
            current += timedelta(days=1)
        
        # Find missing
        missing_dates = sorted(expected_dates - dates_with_data)
        
        if missing_dates:
            self.stdout.write(
                self.style.WARNING(f'\nFound {len(missing_dates)} missing dates:')
            )
            for missing_date in missing_dates:
                self.stdout.write(f'  {missing_date}')
            
            # Generate command to fetch missing dates
            self.stdout.write('\n' + self.style.SUCCESS('To fetch missing dates, run:'))
            for missing_date in missing_dates:
                self.stdout.write(
                    f'python manage.py fetch_historical_scada --date {missing_date}'
                )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'✓ All dates from {start_date} to {end_date} have data!')
            )