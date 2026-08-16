# siren_web/management/commands/extract_esoo_figures.py
"""
Runs a vintage's registered FIGURE_EXTRACTORS mapping(s) and loads the
results into EsooFigure (FR-F02/F03/F04). Tries the structured workbook
source first (esoo_workbook_parser) and the PDF fallback second
(esoo_pdf_parser), per FR-F02's structured-source-first priority — where
both cover the same natural key (e.g. the PDF's rounded Expected-scenario
figures vs. the workbook's full-precision equivalents), the workbook's
values are applied last and win.
"""
from django.core.management.base import BaseCommand
from django.db import connection

from siren_web.models import EsooVintage, EsooFigure
from powerplotui.services.esoo_pdf_parser import parse_esoo_pdf_to_figures
from powerplotui.services.esoo_workbook_parser import parse_esoo_workbook_to_figures

KEY_FIELDS = ('domain', 'metric', 'forecast_year', 'demand_growth_scenario', 'poe_level', 'demand_basis')


class Command(BaseCommand):
    help = "Extract a vintage's demand/supply-adequacy figures (structured source first, PDF fallback) and load them into EsooFigure"

    def add_arguments(self, parser):
        parser.add_argument('--year', type=int, required=True, help='ESOO vintage year to extract')
        parser.add_argument('--dry-run', action='store_true', help='Print extracted figures without writing to the database')
        parser.add_argument('--pdf-only', action='store_true', help='Skip the structured workbook source')
        parser.add_argument('--workbook-only', action='store_true', help='Skip the PDF fallback source')

    def handle(self, *args, **options):
        year = options['year']
        try:
            vintage = EsooVintage.objects.get(year=year)
        except EsooVintage.DoesNotExist:
            self.stdout.write(self.style.ERROR(
                f'No EsooVintage for {year}; run `ingest_esoo_vintage --year {year}` first.'
            ))
            return

        # Table/sheet extraction below is CPU-bound and can run long enough
        # (128-page PDF table extraction, 20MB+ workbook scan) that a
        # low-wait_timeout MySQL server closes the connection opened above
        # while it's idle, causing "MySQL server has gone away" on the
        # first write afterward — with nothing committed. Close it
        # explicitly so Django transparently opens a fresh one on the next
        # query rather than reusing a connection MySQL has already dropped.
        connection.close()

        pdf_figures = []
        if not options['workbook_only']:
            try:
                pdf_figures = parse_esoo_pdf_to_figures(vintage)
                self.stdout.write(f'PDF fallback: {len(pdf_figures)} candidate figure(s).')
            except (NotImplementedError, ValueError) as e:
                self.stdout.write(self.style.WARNING(f'PDF fallback skipped: {e}'))

        connection.close()  # same reasoning — the workbook path also does a DB lookup then slow local parsing

        workbook_figures = []
        if not options['pdf_only']:
            try:
                workbook_figures = parse_esoo_workbook_to_figures(vintage)
                self.stdout.write(f'Structured workbook: {len(workbook_figures)} candidate figure(s).')
            except (NotImplementedError, ValueError) as e:
                self.stdout.write(self.style.WARNING(f'Structured workbook skipped: {e}'))

        if not pdf_figures and not workbook_figures:
            self.stdout.write(self.style.ERROR('Nothing extracted from either source.'))
            return

        # Structured source applied last so it wins where both cover the
        # same natural key (FR-F02 priority).
        ordered_figures = pdf_figures + workbook_figures

        if options['dry_run']:
            for f in ordered_figures:
                self.stdout.write(
                    f"  [{f.get('extraction_method', '?')}] {f['domain']}/{f['metric']} {f['forecast_year']} "
                    f"{f.get('demand_growth_scenario')} POE{f.get('poe_level') or '-'} "
                    f"= {f['value']} {f['unit']}  [{f.get('table_ref')} p.{f.get('page_ref')}]"
                )
            self.stdout.write(self.style.WARNING(f'Dry run — {len(ordered_figures)} figure(s), nothing written.'))
            return

        created, updated = 0, 0
        for f in ordered_figures:
            key = {field: f[field] for field in KEY_FIELDS}
            key['vintage'] = vintage
            defaults = {k: v for k, v in f.items() if k not in KEY_FIELDS}
            _, was_created = EsooFigure.objects.update_or_create(**key, defaults=defaults)
            if was_created:
                created += 1
            else:
                updated += 1

        self.stdout.write(self.style.SUCCESS(f'Loaded: {created} created, {updated} updated.'))
        self.stdout.write(f'Next: python manage.py validate_esoo_data --year {year}')
