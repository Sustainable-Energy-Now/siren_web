"""
Fill gaps in the half-hourly wholesale price series from AEMO's 5-minute
dispatch solutions.

The WEM Reference Trading Price for a 30-minute trading interval is the
average of the six energy Market Clearing Prices of its dispatch
intervals. AEMO's referenceTradingPrice archive occasionally omits
intervals that the dispatchData archive still has, so a missing half-hour
can be reconstructed exactly (validated 2026-09-29 against 40 published
intervals on 4 Nov 2025: all within $0.005/MWh).

Only intervals that are still empty are written, and only when all six
binding dispatch prices exist. Published Reference Trading Prices are
never overwritten.

Each dispatchData archive covers one WEM trading day (08:00 -> 08:00 AWST)
and is large (~235 MB), so pass just the trading days that have gaps.

Usage:
    python manage.py fill_price_gaps_from_dispatch --date 2025-11-30
    python manage.py fill_price_gaps_from_dispatch --date 2025-06-24 --dry-run
"""
import io
import json
import re
import zipfile
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import requests
from django.core.management.base import BaseCommand, CommandError

from siren_web.services.wholesale_price_matrix import set_price_values, values_for_datetime_range

AWST = ZoneInfo('Australia/Perth')
BASE_URL = 'https://data.wa.aemo.com.au/public/market-data/wemde/dispatchSolution/dispatchData/previous/'
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}


class Command(BaseCommand):
    help = "Fill missing half-hourly wholesale prices from AEMO's 5-minute dispatch Market Clearing Prices"

    def add_arguments(self, parser):
        parser.add_argument('--date', type=str, action='append', required=True,
                            help='WEM trading day (YYYY-MM-DD); repeat for several days')
        parser.add_argument('--dry-run', action='store_true',
                            help='Report what would be filled without writing')

    def handle(self, *args, **options):
        listing = requests.get(BASE_URL, headers=HEADERS, timeout=120)
        listing.raise_for_status()
        archive_names = re.findall(r'HREF="[^"]+">([^<]+\.zip)</A>', listing.text)

        for date_str in options['date']:
            try:
                trading_day = datetime.strptime(date_str, '%Y-%m-%d')
            except ValueError:
                raise CommandError(f'Invalid date: {date_str}')
            self.fill_day(trading_day, archive_names, options['dry_run'])

    def fill_day(self, trading_day, archive_names, dry_run):
        start = trading_day.replace(hour=8, tzinfo=AWST)
        stored = values_for_datetime_range(start, start + timedelta(days=1))
        missing_idx = np.flatnonzero(np.isnan(stored))
        label = trading_day.strftime('%Y-%m-%d')
        if missing_idx.size == 0:
            self.stdout.write(f'{label}: no gaps')
            return

        # Base archive plus any reissues (_1, _2 ...); later reissues win.
        stem = f"DispatchSolutionReference_{trading_day.strftime('%Y%m%d')}"
        files = sorted(n for n in archive_names if n == f'{stem}.zip' or n.startswith(f'{stem}_'))
        if not files:
            self.stdout.write(self.style.WARNING(f'{label}: no dispatch archive published'))
            return

        mcp = {}
        for name in files:
            self.stdout.write(f'{label}: downloading {name} ...')
            response = requests.get(BASE_URL + name, headers=HEADERS, timeout=900)
            response.raise_for_status()
            with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
                for member in archive.namelist():
                    data = json.load(archive.open(member))['data']
                    primary = datetime.fromisoformat(data['primaryDispatchInterval'])
                    # Each file also carries look-ahead solutions for later
                    # intervals; only the primary interval's is binding.
                    for solution in data.get('solutionData', []):
                        if (solution.get('dispatchType') == 'Dispatch'
                                and datetime.fromisoformat(solution['dispatchInterval']) == primary):
                            mcp[primary] = float(solution['prices']['energy'])

        records = []
        unfillable = []
        for i in missing_idx:
            t0 = start + timedelta(minutes=30 * int(i))
            dispatch_intervals = [t0 + timedelta(minutes=5 * k) for k in range(6)]
            if all(t in mcp for t in dispatch_intervals):
                records.append({
                    'trading_interval': t0,
                    'wholesale_price': float(np.mean([mcp[t] for t in dispatch_intervals])),
                })
            else:
                unfillable.append(t0.strftime('%H:%M'))

        if records and not dry_run:
            set_price_values(records)
        verb = 'would fill' if dry_run else 'filled'
        self.stdout.write(self.style.SUCCESS(
            f'{label}: {verb} {len(records)} of {missing_idx.size} missing intervals'
        ))
        if unfillable:
            self.stdout.write(self.style.WARNING(
                f'{label}: {len(unfillable)} intervals also missing from dispatch data '
                f'(AWST): {", ".join(unfillable)}'
            ))
