# siren_web/management/commands/register_local_esoo_files.py
"""
Bulk-registers manually downloaded ESOO documents already sitting under
ESOO_ARCHIVE_DIR/{year}/ into EsooVintage / SourceDocument, without
re-downloading them (FR-F01's checksum/manifest requirement). Use this
after downloading a batch of historical vintages by hand — e.g. where
AEMO's site layout or a Cloudflare challenge makes scripted retrieval
impractical for older editions.

Filename -> doc_type is inferred heuristically, since AEMO has used several
different naming/publication conventions across years (confirmed 2017-2025):
  - .pdf                                        -> report
  - .xlsb                                       -> demand_traces
  - .xlsx containing 'table' (case-insensitive) -> data_register_tables
  - .xlsx (anything else)                       -> data_register
  - anything else                               -> skipped, reported as unrecognised
"""
import hashlib
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from siren_web.models import EsooVintage, SourceDocument


def _checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _infer_doc_type(filename: str):
    lower = filename.lower()
    if lower.endswith('.pdf'):
        return 'report'
    if lower.endswith('.xlsb'):
        return 'demand_traces'
    if lower.endswith('.xlsx'):
        return 'data_register_tables' if 'table' in lower else 'data_register'
    return None


class Command(BaseCommand):
    help = 'Bulk-register manually downloaded ESOO documents already on disk under ESOO_ARCHIVE_DIR'

    def add_arguments(self, parser):
        parser.add_argument(
            '--tier', type=str, choices=['modern_comparable', 'heritage'],
            default='modern_comparable', help='Tier to assign newly-registered vintages (default: modern_comparable)',
        )
        parser.add_argument('--dry-run', action='store_true', help='Report what would be registered without writing')
        parser.add_argument('--force', action='store_true', help='Re-checksum/re-register even if already registered')
        parser.add_argument(
            '--exclude-years', type=str, default='',
            help=(
                "Comma-separated years to skip entirely, e.g. for a folder whose file isn't "
                "actually a standalone ESOO edition for that year (register it manually instead)."
            ),
        )

    def handle(self, *args, **options):
        archive_dir = Path(settings.ESOO_ARCHIVE_DIR)
        if not archive_dir.exists():
            self.stdout.write(self.style.ERROR(f'{archive_dir} does not exist'))
            return

        dry_run = options['dry_run']
        tier = options['tier']
        force = options['force']
        exclude_years = {int(y) for y in options['exclude_years'].split(',') if y.strip()}

        year_dirs = sorted(
            (p for p in archive_dir.iterdir() if p.is_dir() and p.name.isdigit() and int(p.name) not in exclude_years),
            key=lambda p: int(p.name),
        )

        registered, skipped, unrecognised = 0, 0, 0

        for year_dir in year_dirs:
            year = int(year_dir.name)
            files = sorted(p for p in year_dir.iterdir() if p.is_file())
            if not files:
                self.stdout.write(self.style.WARNING(f'{year}: no files found — skipped'))
                continue

            self.stdout.write(f'{year}:')
            vintage = None
            if not dry_run:
                vintage, _ = EsooVintage.objects.get_or_create(year=year, defaults={'tier': tier})

            for file_path in files:
                doc_type = _infer_doc_type(file_path.name)
                if doc_type is None:
                    self.stdout.write(self.style.WARNING(f'  ? {file_path.name} — unrecognised type, skipped'))
                    unrecognised += 1
                    continue

                if dry_run:
                    self.stdout.write(f'  would register [{doc_type}] {file_path.name}')
                    continue

                # .as_posix() (not str(Path)) so this is read correctly
                # regardless of which OS ends up serving the site later.
                rel_path = file_path.relative_to(archive_dir).as_posix()

                if doc_type == 'report':
                    if vintage.local_file_path and not force:
                        self.stdout.write(f'  = [report] already registered, skipped')
                        skipped += 1
                        continue
                    vintage.tier = tier
                    vintage.local_file_path = rel_path
                    vintage.checksum = _checksum(file_path)
                    vintage.ingestion_status = 'retrieved'
                    vintage.save()
                    self.stdout.write(self.style.SUCCESS(f'  + [report] {file_path.name}'))
                    registered += 1
                else:
                    doc, _ = SourceDocument.objects.get_or_create(esoo_vintage=vintage, doc_type=doc_type)
                    if doc.local_file_path and not force:
                        self.stdout.write(f'  = [{doc_type}] already registered, skipped')
                        skipped += 1
                        continue
                    doc.local_file_path = rel_path
                    doc.checksum = _checksum(file_path)
                    doc.retrieved_at = timezone.now()
                    doc.save()
                    self.stdout.write(self.style.SUCCESS(f'  + [{doc_type}] {file_path.name}'))
                    registered += 1

        self.stdout.write('\n' + '=' * 60)
        if dry_run:
            self.stdout.write(self.style.WARNING('Dry run — nothing written.'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Registered: {registered}   Skipped (already registered): {skipped}   Unrecognised: {unrecognised}'))
        self.stdout.write('=' * 60)
