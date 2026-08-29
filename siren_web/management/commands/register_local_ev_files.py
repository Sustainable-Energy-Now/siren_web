# siren_web/management/commands/register_local_ev_files.py
"""
Bulk-registers manually downloaded CSIRO EV Projections / AEMO ISP
Step Change files already sitting under EV_ARCHIVE_DIR/{version}/ into
EvVintage / EvSourceDocument, without re-downloading them (mirrors
register_local_esoo_files.py's manifest/checksum discipline).

Filename -> doc_type is inferred against the REAL file names in the
CSIRO Data Shop's "EV Uptake Projections" export and AEMO's IASR EV
workbook (both inspected directly, 2026-08-26 — not a guessed contract):
  - 'FLEET_CONSUMPTION_PROJECTIONS_<TECH>_POSTCODE_WA_*.csv' -> csiro_postcode_fleet_csv
    (one file per TECH_TYPE: BEV/PHEV/HV/HYB/ICE — genuinely five files,
    not one "core dataset"; see ev_uptake_parser.py)
  - 'WA_SUMMARY_*.csv'                      -> csiro_summary (state-level, no postcode column)
  - filename contains 'aemo' or 'isp'       -> aemo_isp_step_change
  - filename contains 'scenarioassumptions' -> csiro_report (methodology/definitions workbook)
  - anything else (.csv/.xlsx/.xls)         -> csiro_report fallback (logged, not silently dropped)
  - anything else                           -> skipped, reported as unrecognised

EvVintage.local_file_path is deliberately left unset by this command:
the real CSIRO release has no single "core dataset" file to point it at
(it's the five EvSourceDocument rows above), so extract_ev_figures reads
the vintage's whole archive folder rather than a single local_file_path.
"""
import hashlib
import re
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from siren_web.models import EvSourceDocument, EvVintage

_FLEET_CSV_RE = re.compile(r'^FLEET_CONSUMPTION_PROJECTIONS_[A-Z]+_POSTCODE_.*\.csv$', re.IGNORECASE)


def _checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _infer_doc_type(filename: str):
    lower = filename.lower()
    if _FLEET_CSV_RE.match(filename):
        return 'csiro_postcode_fleet_csv'
    if lower.startswith('wa_summary') and lower.endswith('.csv'):
        return 'csiro_summary'
    if 'aemo' in lower or 'isp' in lower:
        return 'aemo_isp_step_change'
    if lower.endswith(('.csv', '.xlsx', '.xls')):
        return 'csiro_report'
    return None


class Command(BaseCommand):
    help = 'Bulk-register manually downloaded EV documents already on disk under EV_ARCHIVE_DIR'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Report what would be registered without writing')
        parser.add_argument('--force', action='store_true', help='Re-checksum/re-register even if already registered')

    def handle(self, *args, **options):
        archive_dir = Path(settings.EV_ARCHIVE_DIR)
        if not archive_dir.exists():
            self.stdout.write(self.style.ERROR(f'{archive_dir} does not exist'))
            return

        dry_run = options['dry_run']
        force = options['force']

        version_dirs = sorted(p for p in archive_dir.iterdir() if p.is_dir())
        registered, skipped, unrecognised = 0, 0, 0

        for version_dir in version_dirs:
            version = version_dir.name
            files = sorted(p for p in version_dir.iterdir() if p.is_file())
            if not files:
                self.stdout.write(self.style.WARNING(f'{version}: no files found — skipped'))
                continue

            self.stdout.write(f'{version}:')
            vintage = None
            if not dry_run:
                vintage, _ = EvVintage.objects.get_or_create(version=version)

            for file_path in files:
                doc_type = _infer_doc_type(file_path.name)
                if doc_type is None:
                    self.stdout.write(self.style.WARNING(f'  ? {file_path.name} — unrecognised type, skipped'))
                    unrecognised += 1
                    continue

                if dry_run:
                    self.stdout.write(f'  would register [{doc_type}] {file_path.name}')
                    continue

                rel_path = file_path.relative_to(archive_dir).as_posix()

                doc = EvSourceDocument.objects.filter(vintage=vintage, doc_type=doc_type, local_file_path=rel_path).first()
                if doc and not force:
                    self.stdout.write(f'  = [{doc_type}] {file_path.name} already registered, skipped')
                    skipped += 1
                    continue

                doc = doc or EvSourceDocument(vintage=vintage, doc_type=doc_type, local_file_path=rel_path)
                doc.checksum = _checksum(file_path)
                doc.retrieved_at = timezone.now()
                doc.save()
                self.stdout.write(self.style.SUCCESS(f'  + [{doc_type}] {file_path.name}'))
                registered += 1

            if vintage and vintage.ingestion_status == 'pending':
                vintage.ingestion_status = 'retrieved'
                vintage.save(update_fields=['ingestion_status'])

        self.stdout.write('\n' + '=' * 60)
        if dry_run:
            self.stdout.write(self.style.WARNING('Dry run — nothing written.'))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'Registered: {registered}   Skipped (already registered): {skipped}   Unrecognised: {unrecognised}'
            ))
        self.stdout.write('=' * 60)
