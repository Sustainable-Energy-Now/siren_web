# siren_web/management/commands/load_ev_charging_profile.py
"""
FR-03 — load AEMO's IASR EV workbook (registered as an EvSourceDocument,
doc_type='aemo_isp_step_change', under a given EvVintage) into
EvChargingProfile rows.

Not one of the implementation plan's original five commands (Section
4.3): the plan attributes FR-03 to ingest_ev_vintage, but that command's
job is registering/downloading the raw file (mirroring
ingest_esoo_vintage exactly). Extracting structured rows out of a
registered document is exactly what extract_ev_figures does for the
CSIRO postcode dataset -- this is that same step for the AEMO workbook,
split out as its own command for the same reason extract_ev_figures is
separate from ingest_ev_vintage/register_local_ev_files.
"""
from pathlib import Path

import openpyxl
from django.conf import settings
from django.core.management.base import BaseCommand

from powerplotui.services.ev_charging_profile_parser import (
    EvChargingProfileParseError,
    build_ev_charging_profile_rows,
)
from siren_web.models import EvChargingProfile, EvSourceDocument, EvVintage

KEY_FIELDS = ('region', 'charging_type_label')


class Command(BaseCommand):
    help = "Load AEMO IASR EV workbook charging-type shapes into EvChargingProfile (FR-03)"

    def add_arguments(self, parser):
        parser.add_argument('--vintage', type=str, required=True, help='EvVintage version the AEMO workbook is registered under')
        parser.add_argument('--region', type=str, default='WEM', help="Source region, e.g. 'WEM' (WA) — default WEM")
        parser.add_argument('--scenario', type=str, default='Step Change', help="AEMO scenario to read share_of_charging from (D8 pins Step Change)")
        parser.add_argument(
            '--profile-year', type=int, default=2040,
            help='Financial year (start year) to read charging-type shares for; the kW shape sheets are a single fixed snapshot year regardless (default 2040, matching the workbook\'s own documented snapshot)',
        )
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        version = options['vintage']
        try:
            vintage = EvVintage.objects.get(version=version)
        except EvVintage.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"No EvVintage '{version}'"))
            return

        try:
            source_doc = EvSourceDocument.objects.get(vintage=vintage, doc_type='aemo_isp_step_change')
        except EvSourceDocument.DoesNotExist:
            self.stdout.write(self.style.ERROR(
                f"No aemo_isp_step_change EvSourceDocument registered under vintage '{version}' — "
                "register the AEMO workbook first (register_local_ev_files)."
            ))
            return

        if not source_doc.local_file_path:
            self.stdout.write(self.style.ERROR(f'EvSourceDocument {source_doc.idevsourcedocument} has no local_file_path'))
            return

        path = Path(settings.EV_ARCHIVE_DIR) / source_doc.local_file_path
        if not path.exists():
            self.stdout.write(self.style.ERROR(f'{path} does not exist'))
            return

        workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
        try:
            rows = build_ev_charging_profile_rows(
                workbook, region=options['region'], scenario=options['scenario'], target_year=options['profile_year'],
                report_citation=f"AEMO IASR EV workbook ({version})", table_ref='BEV_PHEV_Charge_Type (%) / BEV_PHEV_Profile_kW',
            )
        except EvChargingProfileParseError as e:
            self.stdout.write(self.style.ERROR(f'Parse failed: {e}'))
            return

        unmatched = None
        clean_rows = []
        for r in rows:
            if '_unmatched_share_labels' in r:
                unmatched = r['_unmatched_share_labels']
            else:
                clean_rows.append(r)

        if not clean_rows:
            self.stdout.write(self.style.ERROR('No charging-type rows extracted.'))
            return

        if options['dry_run']:
            for r in clean_rows:
                self.stdout.write(
                    f"  [{r['charging_mode']:9s}] {r['region']}/{r['charging_type_label']}: "
                    f"share={r['share_of_charging']:.4f}"
                )
            if unmatched:
                self.stdout.write(self.style.WARNING(
                    f"  {len(unmatched)} charging-type label(s) have a fleet share but no static shape "
                    f"(expected for AEMO's dynamically-computed types, e.g. TOU Dynamic Charging): {unmatched}"
                ))
            self.stdout.write(self.style.WARNING(f'Dry run — {len(clean_rows)} row(s), nothing written.'))
            return

        created, updated = 0, 0
        for r in clean_rows:
            key = {field: r[field] for field in KEY_FIELDS}
            key['source_document'] = source_doc
            defaults = {k: v for k, v in r.items() if k not in KEY_FIELDS}
            _, was_created = EvChargingProfile.objects.update_or_create(**key, defaults=defaults)
            created += 1 if was_created else 0
            updated += 0 if was_created else 1

        mode_counts = {}
        for r in clean_rows:
            mode_counts[r['charging_mode']] = mode_counts.get(r['charging_mode'], 0) + 1

        self.stdout.write(self.style.SUCCESS(f'EvChargingProfile: {created} created, {updated} updated.'))
        self.stdout.write(f"By mode: {mode_counts}")
        if unmatched:
            self.stdout.write(self.style.WARNING(
                f"{len(unmatched)} charging-type label(s) have a fleet share but no static shape, excluded: {unmatched}"
            ))
