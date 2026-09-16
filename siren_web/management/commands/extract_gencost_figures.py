# siren_web/management/commands/extract_gencost_figures.py
"""
Parses a GenCost vintage's Appendix Tables workbook (preferring the Final
release, falling back to the Consultation draft if no Final exists yet)
into GencostCostFigure rows, and stubs out a GencostTechnologyMapping row
(technology=None) for any raw technology label not seen before, so
unmapped labels surface on the mapping review page.
"""
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from powerplotui.services.gencost_workbook_parser import open_workbook, parse_capex_sheets
from siren_web.models import GencostCostFigure, GencostTechnologyMapping, GencostVintage

UPDATE_FIELDS = ('value', 'unit', 'sheet_ref')


class Command(BaseCommand):
    help = "Extract a GenCost vintage's capital-cost-by-scenario figures into GencostCostFigure"

    def add_arguments(self, parser):
        parser.add_argument('--vintage', type=str, required=True, help="GenCost edition to extract, e.g. '2025-26'")
        parser.add_argument('--dry-run', action='store_true', help='Print extracted figures without writing to the database')

    def handle(self, *args, **options):
        edition = options['vintage']
        try:
            vintage = GencostVintage.objects.get(edition=edition)
        except GencostVintage.DoesNotExist:
            self.stdout.write(self.style.ERROR(
                f"No GencostVintage '{edition}'; run `fetch_gencost_vintages` "
                f"or upload a workbook for it first."
            ))
            return

        doc = vintage.source_documents.filter(doc_type='gencost_workbook_final').first() \
            or vintage.source_documents.filter(doc_type='gencost_workbook_consult').first()
        if doc is None or not doc.local_file_path:
            self.stdout.write(self.style.ERROR(f"No workbook registered for GenCost {edition}."))
            return

        workbook_path = Path(settings.GENCOST_ARCHIVE_DIR) / doc.local_file_path
        wb = open_workbook(workbook_path)
        figures = parse_capex_sheets(wb)

        if not figures:
            self.stdout.write(self.style.ERROR(f"Nothing extracted from {workbook_path.name}."))
            return

        if options['dry_run']:
            for f in figures:
                self.stdout.write(
                    f"  [{f['sheet_ref']}] {f['raw_technology_label']} {f['cost_case']}/{f['cost_component']} "
                    f"{f['financial_year']} = {f['value']} {f['unit']}"
                )
            self.stdout.write(self.style.WARNING(f'Dry run — {len(figures)} figure(s), nothing written.'))
            return

        # One (or a few, batched) INSERT ... ON DUPLICATE KEY UPDATE rather
        # than ~2000 individual update_or_create round-trips -- the latter
        # took several minutes against this project's remote MariaDB host.
        # MySQL/MariaDB's ON DUPLICATE KEY UPDATE fires on any unique-key
        # violation, so Django's MySQL backend rejects an explicit
        # unique_fields (there's only the one non-PK unique constraint on
        # this table anyway, so the ambiguity Django is guarding against
        # doesn't apply here).
        before = GencostCostFigure.objects.filter(vintage=vintage).count()
        objs = [
            GencostCostFigure(vintage=vintage, **{field: value for field, value in fig.items() if field != 'vintage'})
            for fig in figures
        ]
        GencostCostFigure.objects.bulk_create(objs, update_conflicts=True, update_fields=UPDATE_FIELDS)
        after = GencostCostFigure.objects.filter(vintage=vintage).count()
        created = after - before
        updated = len(figures) - created

        raw_labels = {f['raw_technology_label'] for f in figures}
        existing_labels = set(
            GencostTechnologyMapping.objects.filter(raw_technology_label__in=raw_labels)
            .values_list('raw_technology_label', flat=True)
        )
        new_stubs = [
            GencostTechnologyMapping(raw_technology_label=label)
            for label in raw_labels - existing_labels
        ]
        if new_stubs:
            GencostTechnologyMapping.objects.bulk_create(new_stubs)

        self.stdout.write(self.style.SUCCESS(f'Loaded: {created} created, {updated} updated.'))
        if new_stubs:
            self.stdout.write(self.style.WARNING(
                f'{len(new_stubs)} new technology label(s) need mapping - see the mapping review page.'
            ))
        self.stdout.write(f'Next: python manage.py apply_gencost_cost_case --vintage {edition} --case <case> --dry-run')
