# siren_web/management/commands/fetch_gencost_vintages.py
from django.core.management.base import BaseCommand

from powerplotui.services.gencost_vintage_fetcher import fetch_all_vintages


class Command(BaseCommand):
    help = (
        'Fetch every file in the CSIRO GenCost Data Access Portal collection '
        '(csiro:44228) and register any not already retrieved as a GencostVintage '
        '+ SourceDocument. Idempotent -- safe to run on a schedule.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true', help='Re-download and re-register even if already retrieved')

    def handle(self, *args, **options):
        results = fetch_all_vintages(force=options['force'])

        for filename in results['fetched']:
            self.stdout.write(self.style.SUCCESS(f"  + {filename}"))
        for filename in results['skipped']:
            self.stdout.write(f"  = {filename} (already retrieved)")
        for filename in results['unrecognised']:
            self.stdout.write(self.style.WARNING(f"  ? {filename} (unrecognised naming pattern, skipped)"))

        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS(
            f"Fetched: {len(results['fetched'])}   "
            f"Already retrieved: {len(results['skipped'])}   "
            f"Unrecognised: {len(results['unrecognised'])}"
        ))
        self.stdout.write('=' * 60)
