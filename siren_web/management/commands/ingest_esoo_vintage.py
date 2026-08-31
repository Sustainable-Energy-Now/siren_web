# siren_web/management/commands/ingest_esoo_vintage.py
from django.core.management.base import BaseCommand

from powerplotui.services.esoo_vintage_fetcher import EsooVintageFetcher


class Command(BaseCommand):
    help = (
        'Retrieve WEM ESOO vintage document(s) and record them in the FR-F01 '
        'acquisition manifest (EsooVintage), with checksum and provenance.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--year', type=int, help='Single ESOO publication year to fetch, e.g. 2024')
        parser.add_argument('--years', type=str, help='Range of years to fetch, e.g. 2016-2024')
        parser.add_argument('--url', type=str, help='Override the source URL (only valid with a single --year)')
        parser.add_argument(
            '--tier', type=str, choices=['modern_comparable', 'heritage'],
            default='modern_comparable', help='Archive tier per D4 (default: modern_comparable)',
        )
        parser.add_argument('--force', action='store_true', help='Re-fetch even if already retrieved')
        parser.add_argument(
            '--doc-type', type=str, choices=['report', 'data_register', 'demand_traces'],
            default='report',
            help=(
                "Which document to fetch (default: report, the main PDF). "
                "'data_register'/'demand_traces' require --year (single vintage) "
                "and are stored on SourceDocument, not EsooVintage."
            ),
        )

    def handle(self, *args, **options):
        fetcher = EsooVintageFetcher()
        doc_type = options['doc_type']

        if doc_type != 'report':
            if not options['year']:
                self.stdout.write(self.style.ERROR(f"--doc-type {doc_type} requires --year"))
                return
            try:
                doc = fetcher.fetch_source_document(
                    options['year'], doc_type, url=options.get('url'), force=options['force'],
                )
                self.stdout.write(self.style.SUCCESS(f"  ✓ {options['year']} {doc_type} → {doc.local_file_path}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  ✗ {options['year']} {doc_type}: {e}"))
            return

        if options['year']:
            years = [options['year']]
        elif options['years']:
            try:
                start, end = (int(x) for x in options['years'].split('-'))
            except ValueError:
                self.stdout.write(self.style.ERROR("--years must be formatted like 2016-2024"))
                return
            years = list(range(start, end + 1))
        else:
            self.stdout.write(self.style.ERROR('Specify --year or --years (e.g. --years 2016-2024)'))
            return

        if options['url'] and len(years) > 1:
            self.stdout.write(self.style.ERROR('--url can only be used together with a single --year'))
            return

        self.stdout.write(f"Fetching {len(years)} ESOO vintage(s): {years}...")
        succeeded, failed = 0, 0
        for year in years:
            try:
                vintage = fetcher.fetch_vintage(
                    year, tier=options['tier'], url=options.get('url'), force=options['force'],
                )
                succeeded += 1
                self.stdout.write(self.style.SUCCESS(
                    f"  ✓ {year}: {vintage.ingestion_status} → {vintage.local_file_path}"
                ))
            except Exception as e:
                failed += 1
                self.stdout.write(self.style.ERROR(f"  ✗ {year}: {e}"))

        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(f"Retrieved: {succeeded}   Failed: {failed}")
        self.stdout.write('=' * 60)
