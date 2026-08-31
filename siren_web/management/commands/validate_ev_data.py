# siren_web/management/commands/validate_ev_data.py
"""
FR-20 completeness/range checks over EvUptakePostcodeFigure (quarantining
failures rather than trusting them by default), plus the FR-06/07
backcast gate (Section 8's standing principle: nothing downstream is
trusted until FR-07 passes, and an undefined tolerance is recorded as
not-yet-validated, never passing by default).

FR-07 is split into two distinct checks (resolved 2026-08-27, see
powermatchui.utils.ev_reconciliation's DEFAULT_TOLERANCE_PCT comment for
the full rationale):
  1. --wa-summary-backcast: the real pipeline-fidelity gate. Reproduces
     CSIRO's own published WA-STATEWIDE total (WA_SUMMARY_*.csv) from an
     UNFILTERED aggregation of the same postcode figures -- pure
     summation/unit-conversion arithmetic, so a tight tolerance
     (DEFAULT_TOLERANCE_PCT, 0.1%) is appropriate and this IS a pass/fail
     gate.
  2. --wem-reference-vintage: an informational cross-reference only, not
     a gate. Compares the SWIS-filtered aggregate against AEMO's own
     published WEM-region annual total (from the IASR EV workbook) --
     useful context, but AEMO's scenario framework doesn't line up 1:1
     with CSIRO's Low/Medium/High (see the printed caveat), so this is
     reported as a ratio, never pass/fail.
--published-aggregates remains for a manually-supplied SWIS-scoped
reference, if one is ever obtained independently of the AEMO workbook.

FR-08 ("verify base Siren-web demand trace carries no embedded EV load")
is a one-time documented check per the implementation plan's own
acceptance criterion, not a per-row statistical check -- it is not
automated here; record its outcome as a note against the relevant
EvVintage/Phase-0 governance record once performed manually.
"""
import json
from pathlib import Path

import openpyxl
from django.conf import settings
from django.core.management.base import BaseCommand

from powermatchui.utils.ev_reconciliation import (
    DEFAULT_TOLERANCE_PCT,
    aggregate_statewide_annual_energy,
    aggregate_swis_annual_energy,
    run_backcast_gate,
)
from powerplotui.services.ev_charging_profile_parser import EvChargingProfileParseError, parse_wem_annual_totals
from powerplotui.services.ev_uptake_parser import EvUptakeParseError, parse_wa_summary_to_published_aggregates
from siren_web.models import EvUptakePostcodeFigure, EvVintage, SourceDocument, SwisBoundaryMembership


class Command(BaseCommand):
    help = 'Run FR-20 validation checks over EvUptakePostcodeFigure, and the FR-06/07 backcast checks'

    def add_arguments(self, parser):
        parser.add_argument('--vintage', type=str, help='Only validate figures for this EvVintage version')
        parser.add_argument('--dry-run', action='store_true', help='Report without writing validation_status changes')
        parser.add_argument(
            '--wa-summary-backcast', action='store_true',
            help="Run the FR-07 pipeline-fidelity gate against this vintage's registered WA_SUMMARY (csiro_summary) document",
        )
        parser.add_argument(
            '--wem-reference-vintage', type=str,
            help="EvVintage version with an aemo_isp_step_change document registered -- runs the informational WEM cross-reference (not a gate) if given",
        )
        parser.add_argument('--wem-scenario', type=str, default='Step Change', help="AEMO scenario to read for the WEM cross-reference (default: Step Change)")
        parser.add_argument(
            '--published-aggregates', type=str,
            help=(
                "Path to a JSON file of a genuinely SWIS-scoped published annual-energy aggregate, "
                'shaped as [{"csiro_scenario": "low", "forecast_year": 2030, "published_mwh": 123456.0}, ...]. '
                "Never point this at a WA-statewide reference -- use --wa-summary-backcast for that."
            ),
        )
        parser.add_argument(
            '--tolerance-pct', type=float, default=DEFAULT_TOLERANCE_PCT,
            help=f'FR-07 tolerance for --wa-summary-backcast / --published-aggregates (default: {DEFAULT_TOLERANCE_PCT}%%)',
        )

    def handle(self, *args, **options):
        qs = EvUptakePostcodeFigure.objects.select_related('vintage')
        if options['vintage']:
            qs = qs.filter(vintage__version=options['vintage'])

        if not qs.exists():
            self.stdout.write(self.style.WARNING('No EvUptakePostcodeFigure rows to validate.'))
        else:
            self._validate_figures(qs, options['dry_run'])

        if options['wa_summary_backcast']:
            if not options['vintage']:
                self.stdout.write(self.style.ERROR('--wa-summary-backcast requires --vintage'))
            else:
                self._run_wa_summary_backcast(qs, options['vintage'], options.get('tolerance_pct'))

        if options['published_aggregates']:
            self._run_swis_backcast(qs, options['published_aggregates'], options.get('tolerance_pct'))

        if options['wem_reference_vintage']:
            self._run_wem_reference_check(qs, options['wem_reference_vintage'], options['wem_scenario'])

    def _validate_figures(self, qs, dry_run):
        passed, quarantined = 0, 0
        for figure in qs:
            reasons = self._check_completeness(figure)
            if reasons:
                quarantined += 1
                if not dry_run:
                    figure.validation_status = 'failed'
                    figure.validation_notes = '; '.join(reasons)
                    figure.save(update_fields=['validation_status', 'validation_notes'])
                self.stdout.write(self.style.ERROR(
                    f"  ✗ {figure.postcode}/{figure.forecast_year} {figure.csiro_scenario}: {'; '.join(reasons)}"
                ))
            else:
                passed += 1
                if not dry_run:
                    figure.validation_status = 'passed'
                    figure.validation_notes = ''
                    figure.save(update_fields=['validation_status', 'validation_notes'])

        self.stdout.write('\n' + '=' * 60)
        header = 'FIGURE VALIDATION (dry run)' if dry_run else 'FIGURE VALIDATION'
        self.stdout.write(self.style.WARNING(header) if dry_run else self.style.SUCCESS(header))
        self.stdout.write(f"Checked: {passed + quarantined}   Passed: {passed}   Failed: {quarantined}")
        self.stdout.write('=' * 60 + '\n')

    def _check_completeness(self, figure):
        reasons = []
        if figure.consumption_kwh is None and figure.fleet_count is None:
            reasons.append('both consumption_kwh and fleet_count missing')
        if not figure.postcode:
            reasons.append('missing postcode')
        if not figure.forecast_year:
            reasons.append('missing forecast_year')
        return reasons

    def _print_checks(self, title, checks):
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.WARNING(title))
        self.stdout.write('=' * 60)
        for c in checks:
            line = f"  {c.csiro_scenario}/{c.forecast_year}: aggregated={c.aggregated_mwh:,.1f} MWh"
            if c.published_mwh is not None:
                line += f"  published={c.published_mwh:,.1f} MWh"
            if c.error_pct is not None:
                line += f"  error={c.error_pct:.4f}%"
            style = {'passed': self.style.SUCCESS, 'failed': self.style.ERROR}.get(c.status, self.style.WARNING)
            self.stdout.write(style(f"  [{c.status.upper()}] " + line))
            for note in c.notes:
                self.stdout.write(f"      {note}")
        self.stdout.write('=' * 60 + '\n')

    def _run_wa_summary_backcast(self, qs, version, tolerance_pct):
        passed_figures = [
            {'forecast_year': f.forecast_year, 'csiro_scenario': f.csiro_scenario, 'consumption_kwh': f.consumption_kwh}
            for f in qs.filter(validation_status='passed')
        ]
        try:
            vintage = EvVintage.objects.get(version=version)
            published = parse_wa_summary_to_published_aggregates(vintage, Path(settings.EV_ARCHIVE_DIR))
        except (EvVintage.DoesNotExist, EvUptakeParseError) as e:
            self.stdout.write(self.style.ERROR(f'Could not load WA_SUMMARY reference: {e}'))
            return

        aggregated = aggregate_statewide_annual_energy(passed_figures)
        checks = run_backcast_gate(aggregated, published, tolerance_pct=tolerance_pct)
        self._print_checks('FR-07 PIPELINE-FIDELITY BACKCAST (WA statewide, vs WA_SUMMARY)', checks)

    def _run_swis_backcast(self, qs, published_path, tolerance_pct):
        passed_figures = [
            {
                'postcode': f.postcode, 'forecast_year': f.forecast_year,
                'csiro_scenario': f.csiro_scenario, 'consumption_kwh': f.consumption_kwh,
            }
            for f in qs.filter(validation_status='passed')
        ]
        membership_by_postcode = {
            m.postcode: {'membership_status': m.membership_status, 'apportionment_fraction': m.apportionment_fraction}
            for m in SwisBoundaryMembership.objects.all()
        }
        aggregation = aggregate_swis_annual_energy(passed_figures, membership_by_postcode)

        published_raw = json.loads(Path(published_path).read_text())
        published_aggregates_mwh = {
            (row['csiro_scenario'], row['forecast_year']): row['published_mwh'] for row in published_raw
        }

        checks = run_backcast_gate(aggregation.aggregated_mwh, published_aggregates_mwh, tolerance_pct=tolerance_pct)

        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.WARNING('FR-07 SWIS-SCOPED BACKCAST'))
        self.stdout.write('=' * 60)
        if aggregation.excluded_postcodes:
            self.stdout.write(self.style.WARNING(
                f"{len(aggregation.excluded_postcodes)} postcode(s) excluded — no SwisBoundaryMembership row: "
                f"{aggregation.excluded_postcodes[:10]}{'...' if len(aggregation.excluded_postcodes) > 10 else ''}"
            ))
        for c in checks:
            line = f"  {c.csiro_scenario}/{c.forecast_year}: aggregated={c.aggregated_mwh:,.1f} MWh"
            if c.published_mwh is not None:
                line += f"  published={c.published_mwh:,.1f} MWh"
            if c.error_pct is not None:
                line += f"  error={c.error_pct:.4f}%"
            style = {'passed': self.style.SUCCESS, 'failed': self.style.ERROR}.get(c.status, self.style.WARNING)
            self.stdout.write(style(f"  [{c.status.upper()}] " + line))
            for note in c.notes:
                self.stdout.write(f"      {note}")
        self.stdout.write('=' * 60 + '\n')

    def _run_wem_reference_check(self, qs, wem_version, scenario):
        try:
            wem_vintage = EvVintage.objects.get(version=wem_version)
            doc = SourceDocument.objects.get(ev_vintage=wem_vintage, doc_type='aemo_isp_step_change')
        except (EvVintage.DoesNotExist, SourceDocument.DoesNotExist) as e:
            self.stdout.write(self.style.ERROR(f'Could not find AEMO workbook under vintage {wem_version!r}: {e}'))
            return

        path = Path(settings.EV_ARCHIVE_DIR) / doc.local_file_path
        if not path.exists():
            self.stdout.write(self.style.ERROR(f'{path} does not exist'))
            return

        try:
            workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
            wem_gwh = parse_wem_annual_totals(workbook, 'BEV_PHEV_Consumption (GWh)', scenario, 'WEM')
        except EvChargingProfileParseError as e:
            self.stdout.write(self.style.ERROR(f'Could not parse WEM reference: {e}'))
            return

        membership_by_postcode = {
            m.postcode: {'membership_status': m.membership_status, 'apportionment_fraction': m.apportionment_fraction}
            for m in SwisBoundaryMembership.objects.all()
        }
        passed_figures = [
            {
                'postcode': f.postcode, 'forecast_year': f.forecast_year,
                'csiro_scenario': f.csiro_scenario, 'consumption_kwh': f.consumption_kwh,
            }
            for f in qs.filter(validation_status='passed')
        ]
        aggregation = aggregate_swis_annual_energy(passed_figures, membership_by_postcode)

        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.WARNING(f"FR-07 INFORMATIONAL: SWIS aggregate vs AEMO WEM ({scenario}) — NOT a pass/fail gate"))
        self.stdout.write(self.style.WARNING(
            "AEMO's scenario framework does not map 1:1 onto CSIRO's Low/Medium/High; the closest CSIRO "
            "scenario to compare each row against is a working hypothesis, not confirmed."
        ))
        self.stdout.write('=' * 60)
        for (csiro_scenario, year), swis_mwh in sorted(aggregation.aggregated_mwh.items()):
            wem_mwh = wem_gwh.get(year, None)
            if wem_mwh is None:
                continue
            wem_mwh *= 1000.0  # GWh -> MWh
            ratio_pct = (swis_mwh / wem_mwh * 100.0) if wem_mwh else float('inf')
            self.stdout.write(
                f"  {csiro_scenario}/{year}: SWIS(CSIRO)={swis_mwh:,.1f} MWh  "
                f"WEM(AEMO {scenario})={wem_mwh:,.1f} MWh  ratio={ratio_pct:.1f}%"
            )
        self.stdout.write('=' * 60 + '\n')
