# siren_web/management/commands/refresh_ev_actuals.py
"""
FR-19 — one-shot refresh of the WA EV actuals from the Department of
Transport quarterly "electric vehicle licensing data" PDFs. Safe to run
by hand or from cron:

    python manage.py refresh_ev_actuals

What it does, idempotently:
  1. scrape the DoT index page for quarterly-report PDF links
     (--url / --file to process just one; --no-download to re-parse only
     what is already archived)
  2. download any not already in EV_ARCHIVE_DIR/dot_wa_actuals/
  3. parse each PDF's "Figure 1b" cumulative table (BEV/PHEV/Total by
     quarter) — pre-2025 chart-only PDFs yield no series and are kept for
     provenance only
  4. upsert EvActualsDocument (one per PDF) and EvActualsQuarter (one per
     quarter-end; the most recent PDF wins, since DoT revises history)
  5. derive the annual EvActualsRecord rows the tracking dashboard uses
     (one per calendar year = that year's DECEMBER quarter; the current
     year appears only once its Dec report is published, so the annual
     series stays like-for-like with CSIRO's year-end projections)

Exit status is non-zero if nothing could be parsed at all (the PDF
layout probably changed) so a cron wrapper can alert.
"""
import datetime as _dt

import requests
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from powerplotui.services.dot_wa_ev_fetcher import (
    archive_dir, discover_report_urls, fetch_report, register_local_report,
)
from powerplotui.services.dot_wa_ev_parser import DotWaEvParseError, parse_actuals_pdf
from siren_web.models import (
    EvActualsDocument, EvActualsQuarter, EvActualsRecord,
)

SOURCE = 'dot_wa_registrations'
RESOLUTION_CEILING = 'state total (year-end Dec cumulative snapshot; DoT WA licensing data)'


class Command(BaseCommand):
    help = 'Download the DoT WA quarterly EV licensing PDFs and refresh EvActuals* from them'

    def add_arguments(self, parser):
        parser.add_argument('--url', action='append', default=[],
                            help='Process only this report URL (repeatable); skips index scrape')
        parser.add_argument('--file', action='append', default=[],
                            help='Process a local PDF already on disk (repeatable); skips download')
        parser.add_argument('--index-url', default=None, help='Override the DoT index page URL')
        parser.add_argument('--no-download', action='store_true',
                            help='Do not fetch anything new; re-parse only PDFs already archived')
        parser.add_argument('--force', action='store_true',
                            help='Re-download and re-parse even if the PDF is already archived')
        parser.add_argument('--dry-run', action='store_true',
                            help='Report what would change without writing to the database '
                                 '(new PDFs are still downloaded to the archive so they can be parsed)')

    def handle(self, *args, **opts):
        dry_run = opts['dry_run']
        session = requests.Session()

        # --- 1. assemble the list of report dicts to process ---------------
        # Explicit --file / --url win; then --no-download re-parses the
        # archive; otherwise scrape the index and download what's new.
        reports = []
        for path in opts['file']:
            reports.append(register_local_report(path))

        if opts['url']:
            for url in opts['url']:
                try:
                    reports.append(fetch_report(url, force=opts['force'], session=session))
                except (requests.RequestException, ValueError) as e:
                    self.stderr.write(self.style.WARNING(f'  skip {url}: {e}'))
        elif opts['no_download']:
            for pdf in sorted(archive_dir().glob('*.pdf')):
                reports.append(register_local_report(pdf))
        elif not opts['file']:
            try:
                urls = discover_report_urls(opts['index_url'], session=session)
            except requests.RequestException as e:
                raise CommandError(f'Could not read the DoT index page: {e}')
            for url in urls:
                try:
                    reports.append(fetch_report(url, force=opts['force'], session=session))
                except (requests.RequestException, ValueError) as e:
                    self.stderr.write(self.style.WARNING(f'  skip {url}: {e}'))

        if not reports:
            raise CommandError('No reports to process.')

        # --- 2. parse each PDF -------------------------------------------
        parsed = []           # (report_dict, parse_result)
        total_series_rows = 0
        for rpt in reports:
            try:
                result = parse_actuals_pdf(rpt['path'])
            except DotWaEvParseError as e:
                self.stderr.write(self.style.WARNING(f'  unparseable: {e}'))
                continue
            total_series_rows += len(result['series'])
            parsed.append((rpt, result))
            flag = '' if result['series'] else '  (chart-only, provenance only)'
            self.stdout.write(
                f"  {result['quarter_label']}: {len(result['series'])} Figure 1b row(s)"
                f"{flag}  [{rpt['filename']}]"
            )

        if not parsed:
            raise CommandError('No PDF could be parsed at all.')

        if total_series_rows == 0:
            raise CommandError(
                'Every PDF parsed but NONE yielded a Figure 1b series — the '
                'DoT table layout has probably changed. Not writing anything.'
            )

        # --- 3. merge the per-quarter series; newest report wins --------
        # parsed is unordered; sort so a later report's figures overwrite
        # an earlier report's for the same quarter-end.
        parsed.sort(key=lambda pr: pr[1]['period_end'])
        merged = {}           # period_end -> dict(bev, phev, total, doc_key)
        for rpt, result in parsed:
            for row in result['series']:
                merged[row['period_end']] = {
                    'bev': row['bev'], 'phev': row['phev'], 'total': row['total'],
                    'period_end_of_report': result['period_end'],
                }

        if dry_run:
            self._report_dry_run(parsed, merged)
            return

        # --- 4. write ---------------------------------------------------
        with transaction.atomic():
            docs_by_period = self._upsert_documents(parsed)
            n_q = self._upsert_quarters(merged, docs_by_period)
            n_a = self._derive_annual(docs_by_period)

        self.stdout.write(self.style.SUCCESS(
            f'Done. {len(parsed)} document(s), {n_q} quarter row(s), {n_a} annual row(s) upserted.'
        ))

    # ------------------------------------------------------------------
    def _upsert_documents(self, parsed):
        docs_by_period = {}
        for rpt, result in parsed:
            doc, _ = EvActualsDocument.objects.update_or_create(
                source=SOURCE, period_end=result['period_end'],
                defaults={
                    'quarter_label': result['quarter_label'],
                    'source_url': rpt['url'] if rpt['url'].startswith('http') else '',
                    'local_file_path': rpt['local_file_path'],
                    'checksum': rpt['checksum'],
                    'report_prepared_date': result['report_prepared_date'],
                    'series_rows_extracted': len(result['series']),
                    'retrieved_at': timezone.now(),
                },
            )
            docs_by_period[result['period_end']] = doc
        return docs_by_period

    def _upsert_quarters(self, merged, docs_by_period):
        n = 0
        for period_end, fig in sorted(merged.items()):
            doc = docs_by_period.get(fig['period_end_of_report'])
            EvActualsQuarter.objects.update_or_create(
                source=SOURCE, region='WA', period_end=period_end,
                defaults={
                    'bev_count': fig['bev'], 'phev_count': fig['phev'],
                    'total_count': fig['total'], 'document': doc,
                },
            )
            n += 1
        return n

    def _derive_annual(self, docs_by_period):
        """One EvActualsRecord per calendar year = that year's DECEMBER
        (year-end) EvActualsQuarter row. Years with only mid-year quarters
        so far (i.e. the current year) are skipped — a partial-year figure
        is not a like-for-like match for CSIRO's year-end projections, and
        the FR-14 trajectory flag keys off the latest actuals year."""
        year_end = {
            q.period_end.year: q
            for q in EvActualsQuarter.objects.filter(
                source=SOURCE, region='WA', period_end__month=12,
            ).order_by('period_end')
        }

        # Drop any partial-year row a previous run wrote before this year's
        # December quarter existed (e.g. a mid-year current-year figure).
        stale = EvActualsRecord.objects.filter(
            region='WA', source=SOURCE,
        ).exclude(year__in=year_end.keys())
        n_pruned = stale.count()
        stale.delete()

        n = 0
        for year, q in sorted(year_end.items()):
            EvActualsRecord.objects.update_or_create(
                year=year, region='WA', source=SOURCE,
                defaults={
                    'fleet_count': q.total_count,
                    'bev_count': q.bev_count,
                    'phev_count': q.phev_count,
                    'resolution_ceiling': RESOLUTION_CEILING,
                    'period_end': q.period_end,
                    'document': q.document or docs_by_period.get(q.period_end),
                },
            )
            n += 1
        if n_pruned:
            self.stdout.write(f'  pruned {n_pruned} partial-year annual row(s)')
        return n

    # ------------------------------------------------------------------
    def _report_dry_run(self, parsed, merged):
        self.stdout.write(self.style.WARNING('\n--- DRY RUN (no database writes) ---'))
        self.stdout.write(f'{len(parsed)} document(s) would be upserted:')
        for rpt, result in parsed:
            self.stdout.write(
                f"  {result['quarter_label']}  prepared={result['report_prepared_date']}  "
                f"rows={len(result['series'])}  {rpt['filename']}"
            )
        self.stdout.write(f'\n{len(merged)} EvActualsQuarter row(s):')
        for period_end, fig in sorted(merged.items()):
            self.stdout.write(
                f"  {period_end}  BEV={int(fig['bev'])}  PHEV={int(fig['phev'])}  Total={int(fig['total'])}"
            )
        years = {
            period_end.year: (period_end, fig['total'])
            for period_end, fig in sorted(merged.items())
            if period_end.month == 12
        }
        self.stdout.write(f'\n{len(years)} EvActualsRecord (year-end annual) row(s):')
        for year, (period_end, total) in sorted(years.items()):
            self.stdout.write(f"  {year}: {int(total)}  (from {period_end})")
