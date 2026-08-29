# siren_web/management/commands/ingest_ev_vintage.py
"""
FR-01/02/03 — register a new CSIRO EV Projections release / AEMO ISP
Step Change charging-profile document as a pinned EvVintage.

Unlike ingest_esoo_vintage (which downloads from AEMO's own predictable
per-year URL pattern), no such pattern is assumed here for CSIRO/AEMO's
EV-specific publications -- this command takes an explicit --url (or
--file for something already downloaded) rather than guessing a URL
pattern that hasn't been confirmed against a real release. Use
register_local_ev_files for bulk-registering a batch already on disk.
"""
import hashlib
from pathlib import Path

import requests
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from siren_web.models import EvVintage


def _checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Command(BaseCommand):
    help = 'Register a new CSIRO EV Projections release as a pinned EvVintage (FR-01/02)'

    def add_arguments(self, parser):
        parser.add_argument('--vintage', type=str, required=True, help="Release identifier, e.g. '2024-Q3'")
        parser.add_argument('--url', type=str, help='URL to download the core postcode dataset from')
        parser.add_argument('--file', type=str, help='Path to an already-downloaded local file to register instead of downloading')
        parser.add_argument('--release-date', type=str, help='YYYY-MM-DD')
        parser.add_argument('--licence', type=str, default='')
        parser.add_argument('--force', action='store_true', help='Re-fetch/re-register even if already retrieved')

    def handle(self, *args, **options):
        version = options['vintage']
        if not options['url'] and not options['file']:
            self.stdout.write(self.style.ERROR('Specify --url (to download) or --file (already on disk)'))
            return

        vintage, _ = EvVintage.objects.get_or_create(version=version)
        if vintage.ingestion_status in ('retrieved', 'validated') and not options['force']:
            self.stdout.write(self.style.WARNING(
                f"{version} already retrieved (status={vintage.ingestion_status}); use --force to re-fetch."
            ))
            return

        archive_dir = Path(settings.EV_ARCHIVE_DIR) / version
        archive_dir.mkdir(parents=True, exist_ok=True)

        if options['file']:
            src = Path(options['file'])
            if not src.exists():
                self.stdout.write(self.style.ERROR(f'{src} does not exist'))
                return
            dest = archive_dir / src.name
            dest.write_bytes(src.read_bytes())
        else:
            url = options['url']
            try:
                resp = requests.get(url, timeout=60)
                resp.raise_for_status()
            except requests.RequestException as e:
                self.stdout.write(self.style.ERROR(f'Download failed: {e}'))
                return
            filename = url.rstrip('/').split('/')[-1] or f'{version}.dat'
            dest = archive_dir / filename
            dest.write_bytes(resp.content)

        vintage.local_file_path = dest.relative_to(Path(settings.EV_ARCHIVE_DIR)).as_posix()
        vintage.checksum = _checksum(dest)
        vintage.source_url = options.get('url') or ''
        vintage.licence = options['licence']
        if options['release_date']:
            vintage.release_date = options['release_date']
        vintage.ingestion_status = 'retrieved'
        vintage.save()

        self.stdout.write(self.style.SUCCESS(f"  ✓ {version} → {vintage.local_file_path}"))
        self.stdout.write(f"Next: python manage.py extract_ev_figures --vintage {version}")
