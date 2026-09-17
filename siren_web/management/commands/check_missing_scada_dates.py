# powerplot/management/commands/check_missing_scada_dates.py
from django.core.management.base import BaseCommand
from datetime import datetime, timedelta, timezone as dt_timezone

from siren_web.services.facility_scada_matrix import cell_counts_for_datetime_range

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

        # UTC calendar dates, matching dispatch_interval__date's convention
        # under settings.TIME_ZONE='UTC'.
        start_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=dt_timezone.utc)
        end_dt = datetime.combine(end_date + timedelta(days=1), datetime.min.time(), tzinfo=dt_timezone.utc)

        n_days = (end_date - start_date).days + 1
        counts = cell_counts_for_datetime_range(start_dt, end_dt)
        daily_has_data = counts.reshape(n_days, 48).sum(axis=1) > 0

        dates_with_data = {
            start_date + timedelta(days=i) for i in range(n_days) if daily_has_data[i]
        }

        # Generate expected dates
        expected_dates = {start_date + timedelta(days=i) for i in range(n_days)}

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
