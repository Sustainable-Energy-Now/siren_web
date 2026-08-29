# siren_web/management/commands/validate_ev_data.py
"""
FR-20 completeness/range checks over EvUptakePostcodeFigure (quarantining
failures rather than trusting them by default), plus an optional FR-06/07
SWIS backcast gate run (Section 8's standing principle: nothing
downstream is trusted until FR-07 passes, and an undefined tolerance is
recorded as not-yet-validated, never passing by default).

FR-08 ("verify base Siren-web demand trace carries no embedded EV load")
is a one-time documented check per the implementation plan's own
acceptance criterion, not a per-row statistical check -- it is not
automated here; record its outcome as a note against the relevant
EvVintage/Phase-0 governance record once performed manually.
"""
import json
from pathlib import Path

from django.core.management.base import BaseCommand

from powermatchui.utils.ev_reconciliation import aggregate_swis_annual_energy, run_backcast_gate
from siren_web.models import EvUptakePostcodeFigure, SwisBoundaryMembership


class Command(BaseCommand):
    help = 'Run FR-20 validation checks over EvUptakePostcodeFigure, and optionally the FR-07 backcast gate'

    def add_arguments(self, parser):
        parser.add_argument('--vintage', type=str, help='Only validate figures for this EvVintage version')
        parser.add_argument('--dry-run', action='store_true', help='Report without writing validation_status changes')
        parser.add_argument(
            '--published-aggregates', type=str,
            help=(
                "Path to a JSON file of CSIRO's own published SWIS/WA annual-energy aggregates, "
                'shaped as [{"csiro_scenario": "low", "forecast_year": 2030, "published_mwh": 123456.0}, ...]. '
                'Runs the FR-07 backcast gate against this pipeline\'s own aggregation. Omit to skip FR-07 this run.'
            ),
        )
        parser.add_argument('--tolerance-pct', type=float, help='FR-07 tolerance (Section 10 Open Item — confirm with Sprint Leader)')

    def handle(self, *args, **options):
        qs = EvUptakePostcodeFigure.objects.select_related('vintage')
        if options['vintage']:
            qs = qs.filter(vintage__version=options['vintage'])

        if not qs.exists():
            self.stdout.write(self.style.WARNING('No EvUptakePostcodeFigure rows to validate.'))
        else:
            self._validate_figures(qs, options['dry_run'])

        if options['published_aggregates']:
            self._run_backcast_gate(qs, options['published_aggregates'], options.get('tolerance_pct'))

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

    def _run_backcast_gate(self, qs, published_path, tolerance_pct):
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

        checks = run_backcast_gate(aggregation, published_aggregates_mwh, tolerance_pct=tolerance_pct)

        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.WARNING('FR-07 BACKCAST GATE'))
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
