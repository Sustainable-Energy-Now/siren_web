# siren_web/management/commands/extract_ev_figures.py
"""
FR-01/FR-20 — extract a vintage's postcode-level fleet/consumption
figures (structured source only — there is no PDF-fallback path for the
EV postcode dataset, unlike ESOO's report+workbook duality) into
EvUptakePostcodeFigure, and record CSIRO's own privacy-suppressed rows
separately in EvSuppressionFlag rather than treating them as loss.
"""
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from powerplotui.services.ev_uptake_parser import EvUptakeParseError, parse_ev_postcode_dataset_to_figures
from siren_web.models import EvSuppressionFlag, EvUptakePostcodeFigure, EvVintage

KEY_FIELDS = ('postcode', 'forecast_year', 'csiro_scenario')


class Command(BaseCommand):
    help = "Extract a vintage's postcode-level EV figures into EvUptakePostcodeFigure (FR-01/FR-20)"

    def add_arguments(self, parser):
        parser.add_argument('--vintage', type=str, required=True, help='EvVintage version to extract')
        parser.add_argument('--dry-run', action='store_true', help='Print extracted figures without writing to the database')

    def handle(self, *args, **options):
        version = options['vintage']
        try:
            vintage = EvVintage.objects.get(version=version)
        except EvVintage.DoesNotExist:
            self.stdout.write(self.style.ERROR(
                f"No EvVintage '{version}'; run `ingest_ev_vintage --vintage {version} ...` first."
            ))
            return

        try:
            figures, suppression_flags = parse_ev_postcode_dataset_to_figures(vintage, Path(settings.EV_ARCHIVE_DIR))
        except EvUptakeParseError as e:
            self.stdout.write(self.style.ERROR(f'Extraction failed: {e}'))
            return

        if options['dry_run']:
            for f in figures:
                self.stdout.write(
                    f"  {f['postcode']} {f['forecast_year']} {f['csiro_scenario']}: "
                    f"fleet={f['fleet_count']} consumption_kwh={f['consumption_kwh']}"
                )
            self.stdout.write(self.style.WARNING(
                f"Dry run — {len(figures)} figure(s), {len(suppression_flags)} suppression flag(s), nothing written."
            ))
            return

        created, updated = 0, 0
        for f in figures:
            key = {field: f[field] for field in KEY_FIELDS}
            key['vintage'] = vintage
            defaults = {k: v for k, v in f.items() if k not in KEY_FIELDS}
            _, was_created = EvUptakePostcodeFigure.objects.update_or_create(**key, defaults=defaults)
            if was_created:
                created += 1
            else:
                updated += 1

        flags_created = 0
        for sf in suppression_flags:
            key = {field: sf[field] for field in KEY_FIELDS}
            key['vintage'] = vintage
            defaults = {k: v for k, v in sf.items() if k not in KEY_FIELDS}
            _, was_created = EvSuppressionFlag.objects.update_or_create(**key, defaults=defaults)
            if was_created:
                flags_created += 1

        self.stdout.write(self.style.SUCCESS(
            f'Figures: {created} created, {updated} updated. Suppression flags: {flags_created} created.'
        ))
        self.stdout.write(f"Next: python manage.py validate_ev_data --vintage {version}")
