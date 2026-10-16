"""
Management command: check_cel_sources

Polls the published Clean Energy Link sources (CELSourceWatch) for changes,
snapshots changed text, and raises CELProposedUpdate rows from rule-based
extraction for review at /powermapui/cel/proposals/.

Usage:
    python manage.py check_cel_sources              # seed defaults, check all active watches
    python manage.py check_cel_sources --dry-run    # fetch + extract, write nothing
    python manage.py check_cel_sources --url <url>  # check just one watch (added if new)
"""
import requests
from django.core.management.base import BaseCommand, CommandError

from powermapui.utils.cel_proposals import build_refs
from powermapui.utils.cel_source_watcher import check_watch, clean_url, default_watches, seed_default_sources
from siren_web.models import CELSourceWatch


class Command(BaseCommand):
    help = 'Check published CEL sources for changes and propose CEL stage updates'

    def add_arguments(self, parser):
        parser.add_argument('--url', action='append', default=[],
                            help='Check only this URL (repeatable); adds it as a manual watch if new')
        parser.add_argument('--dry-run', action='store_true',
                            help='Fetch and extract but write nothing (no snapshots, proposals or new watches)')

    def handle(self, *args, **opts):
        # Source labels and evidence carry dashes a Windows cp1252 console can't print.
        for stream in (self.stdout, self.stderr):
            getattr(stream._out, 'reconfigure', lambda **kw: None)(errors='replace')
        dry_run = opts['dry_run']
        if not dry_run:
            n = seed_default_sources()
            if n:
                self.stdout.write(f'Seeded {n} default source(s).')

        if opts['url']:
            watches = []
            for raw in opts['url']:
                url = clean_url(raw)
                watch = CELSourceWatch.objects.filter(url=url).first()
                if watch is None:
                    watch = CELSourceWatch(url=url, label=url, origin='manual')
                    if not dry_run:
                        watch.save()
                watches.append(watch)
        else:
            watches = list(CELSourceWatch.objects.filter(is_active=True).order_by('idcelsourcewatch'))
            if not watches and dry_run and not CELSourceWatch.objects.exists():
                # Nothing seeded yet and a dry run mustn't seed: preview the default list unsaved.
                watches = default_watches()
                self.stdout.write('No sources saved yet; previewing the default source list.')
        if not watches:
            raise CommandError('No active CEL source watches.')

        session = requests.Session()
        refs = build_refs()
        totals = {'checked': 0, 'changed': 0, 'errors': 0, 'proposals': 0, 'discovered': 0}
        if dry_run:
            self.stdout.write(self.style.WARNING('--- DRY RUN (no database writes) ---'))

        for watch in watches:
            r = check_watch(watch, session=session, refs=refs, dry_run=dry_run)
            totals['checked'] += 1
            label = watch.label or watch.url
            if r['error']:
                totals['errors'] += 1
                self.stdout.write(self.style.WARNING(f'  ERROR  {label}: {r["error"]}'))
                continue
            state = 'NEW' if r['initial'] else ('CHANGED' if r['changed'] else 'same')
            self.stdout.write(f'  {state:<7} {label}')
            totals['changed'] += r['changed']
            for p in r['proposals']:
                totals['proposals'] += 1
                if dry_run:          # Findings, not saved rows
                    self.stdout.write(f'           would propose {p.field_name} = {p.value} '
                                      f'(program {p.program_id}, stage {p.stage_id or "?"})')
                else:
                    self.stdout.write(f'           proposed {p}')
            for url, _ in r['discovered']:
                totals['discovered'] += 1
                self.stdout.write(f'           {"would add" if dry_run else "added"} watch {url}')

        msg = (f"Done. {totals['checked']} checked, {totals['changed']} changed, "
               f"{totals['proposals']} proposal(s), {totals['discovered']} new source(s), "
               f"{totals['errors']} error(s).")
        self.stdout.write(self.style.SUCCESS(msg) if not totals['errors'] else self.style.WARNING(msg))
        if totals['errors'] == totals['checked']:
            raise CommandError('Every source failed to fetch — check network access.')
