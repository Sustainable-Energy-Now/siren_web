"""
Management command: sync_cel_gis

Reconciles CEL stages against Western Power's published network GIS
(data.wa.gov.au WP-051 transmission lines, WP-049 substations) and raises
CELProposedUpdate rows when a stage's linked lines/terminals have been
built.  Also proposes reserved_capacity_mw derived from the aligned
facilities that are under construction.

Usage:
    python manage.py sync_cel_gis                       # SLIP REST (needs SLIP_USERNAME/PASSWORD)
    python manage.py sync_cel_gis --lines-file wp051.geojson --substations-file wp049.geojson
    python manage.py sync_cel_gis --dry-run
    python manage.py sync_cel_gis --skip-gis            # derived reserved capacity only
"""
import datetime as dt

import requests
from django.core.management.base import BaseCommand

from powermapui.utils.cel_gis_sync import (
    DEFAULT_LINES_URL, DEFAULT_SUBSTATIONS_URL, GisUnavailable, assess_stage,
    derived_reserved_capacity, index_lines, index_substations, load_layer,
)
from powermapui.utils.cel_proposals import create_proposal, format_value, is_improvement
from siren_web.models import CELStage


class Command(BaseCommand):
    help = "Propose CEL stage progress from Western Power's network GIS and aligned facilities"

    def add_arguments(self, parser):
        parser.add_argument('--lines-file', help='GeoJSON of WP-051 instead of fetching from SLIP')
        parser.add_argument('--substations-file', help='GeoJSON of WP-049 instead of fetching from SLIP')
        parser.add_argument('--lines-url', default=DEFAULT_LINES_URL)
        parser.add_argument('--substations-url', default=DEFAULT_SUBSTATIONS_URL)
        parser.add_argument('--skip-gis', action='store_true', help='Only derive reserved capacity')
        parser.add_argument('--dry-run', action='store_true', help='Report without creating proposals')

    def handle(self, *args, **opts):
        # Stage names and evidence carry dashes/arrows a Windows cp1252 console can't print.
        for stream in (self.stdout, self.stderr):
            getattr(stream._out, 'reconfigure', lambda **kw: None)(errors='replace')
        dry_run = opts['dry_run']
        stages = list(CELStage.objects.filter(is_active=True).select_related('cel_program')
                      .order_by('cel_program__name', 'stage_number'))
        if dry_run:
            self.stdout.write(self.style.WARNING('--- DRY RUN (no proposals written) ---'))
        created = 0

        if not opts['skip_gis']:
            session = requests.Session()
            line_index = self._load('lines', opts['lines_file'], opts['lines_url'], session, index_lines)
            sub_index = self._load('substations', opts['substations_file'], opts['substations_url'],
                                   session, index_substations)
            if line_index is not None or sub_index is not None:
                for stage in stages:
                    created += self._gis_stage(stage, line_index, sub_index, dry_run)

        self.stdout.write('\nDerived reserved capacity (aligned facilities under construction):')
        for stage in stages:
            mw, names = derived_reserved_capacity(stage)
            if not is_improvement('reserved_capacity_mw', stage.reserved_capacity_mw, mw):
                continue
            self.stdout.write(f'  {stage}: {stage.reserved_capacity_mw or 0:,.0f} → {mw:,.0f} MW')
            if dry_run:
                continue
            evidence = ('Sum of capacity of facilities aligned to this stage with status '
                        'Under Construction:\n' + ('\n'.join(f'- {n}' for n in names) or '- none'))
            created += bool(create_proposal(
                program_id=stage.cel_program_id, stage=stage, field_name='reserved_capacity_mw',
                value=mw, evidence=evidence, source='derived'))

        self.stdout.write(self.style.SUCCESS(f'\nDone. {created} proposal(s) created.'))

    def _load(self, what, file_path, url, session, indexer):
        try:
            features = load_layer(file_path, url, session=session)
        except GisUnavailable as e:
            self.stdout.write(self.style.WARNING(f'Skipping GIS {what}: {e}'))
            return None
        except (requests.RequestException, ValueError, OSError) as e:
            self.stdout.write(self.style.WARNING(f'Could not load GIS {what}: {e}'))
            return None
        index = indexer(features)
        self.stdout.write(f'Loaded {len(index)} in-service {what} feature(s) from {file_path or url}')
        return index

    def _gis_stage(self, stage, line_index, sub_index, dry_run):
        a = assess_stage(stage, line_index, sub_index)
        self.stdout.write(f'\n{stage}  [{stage.get_funding_status_display()}]')
        if not a.checks:
            self.stdout.write('  no linked grid lines or new terminals to check')
            return 0
        for c in a.checks:
            self.stdout.write(f'  {c.kind:<8} {c.state:<10} {c.name} — {c.detail}')
        if not a.confirmed:
            return 0

        proposals = [('funding_status', 'under_construction')]
        if a.all_built:
            proposals = [('funding_status', 'operational'),
                         ('actual_operational_date', dt.date.today())]
            if stage.actual_operational_date:           # keep a date someone already entered
                proposals.pop()
        n = 0
        for field_name, value in proposals:
            if not is_improvement(field_name, getattr(stage, field_name), value):
                continue
            self.stdout.write(f'  → propose {field_name} = {format_value(field_name, value)}')
            if not dry_run:
                n += bool(create_proposal(program_id=stage.cel_program_id, stage=stage,
                                          field_name=field_name, value=value,
                                          evidence=a.evidence(), source='gis'))
        return n
