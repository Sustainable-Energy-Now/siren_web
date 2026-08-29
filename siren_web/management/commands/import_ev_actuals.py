# siren_web/management/commands/import_ev_actuals.py
"""
FR-19 — ingest the FR-19-selected WA actuals source (D7: DoT WA
registrations, ABS Motor Vehicle Census, or EV Council/FCAI sales index)
into EvActualsRecord. No ESOO analogue: the ESOO pipeline derives actuals
from SCADA (compute_annual_demand_actuals), but EV fleet actuals come
from a registration/census/sales source instead.

Takes a plain CSV (year, region, fleet_count) rather than scraping a
specific agency's site, since FR-19's source review (Section 10 Open
Item) is a Phase 1 deliverable this command does not pre-empt -- point it
at whichever source's exported CSV the review recommends.
"""
import csv
from pathlib import Path

from django.core.management.base import BaseCommand

from siren_web.models import EV_ACTUALS_SOURCE_CHOICES, EvActualsRecord

VALID_SOURCES = {choice[0] for choice in EV_ACTUALS_SOURCE_CHOICES}


class Command(BaseCommand):
    help = 'Ingest the FR-19-selected WA EV actuals source into EvActualsRecord'

    def add_arguments(self, parser):
        parser.add_argument('--csv', type=str, required=True, help='Path to a CSV with columns: year, region, fleet_count')
        parser.add_argument('--source', type=str, required=True, choices=sorted(VALID_SOURCES))
        parser.add_argument(
            '--resolution-ceiling', type=str, default='state total',
            help="Finest geography this source actually supports (O4), e.g. 'state total'",
        )
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        path = Path(options['csv'])
        if not path.exists():
            self.stdout.write(self.style.ERROR(f'{path} does not exist'))
            return

        source = options['source']
        resolution_ceiling = options['resolution_ceiling']
        dry_run = options['dry_run']

        created, updated = 0, 0
        with path.open(newline='') as f:
            reader = csv.DictReader(f)
            missing = [c for c in ('year', 'region', 'fleet_count') if c not in (reader.fieldnames or [])]
            if missing:
                self.stdout.write(self.style.ERROR(f'CSV missing required column(s): {missing}'))
                return

            for row in reader:
                year = int(row['year'])
                region = row['region'].strip() or 'WA'
                fleet_count = float(row['fleet_count'])

                if dry_run:
                    self.stdout.write(f'  would register {year} {region} ({source}): {fleet_count}')
                    continue

                _, was_created = EvActualsRecord.objects.update_or_create(
                    year=year, region=region, source=source,
                    defaults={'fleet_count': fleet_count, 'resolution_ceiling': resolution_ceiling},
                )
                if was_created:
                    created += 1
                else:
                    updated += 1

        if dry_run:
            self.stdout.write(self.style.WARNING('Dry run — nothing written.'))
        else:
            self.stdout.write(self.style.SUCCESS(f'EvActualsRecord: {created} created, {updated} updated.'))
