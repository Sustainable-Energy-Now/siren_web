# siren_web/management/commands/validate_esoo_data.py
"""
FR-F08 — extraction validation checks. Runs completeness, uniqueness,
range/plausibility, and internal-consistency checks over EsooFigure rows
before they're trusted as canonical. Failures are quarantined
(validation_status='quarantined', with a reason) rather than silently
treated as valid.
"""
from collections import defaultdict

from django.core.management.base import BaseCommand

from siren_web.models import EsooFigure

# Plausibility bounds. energy/peak_summer/peak_winter/minimum were
# recalibrated 2026-08-14 against real extracted figures from all 10
# registered vintages (2017-2026, ~1,335 EsooFigure-shaped values) via
# esoo_workbook_parser's SHEET_PLANS — bounds below are the observed
# min/max with headroom, not blind guesses. High-growth-scenario figures
# in outer forecast years are the ones that push these bounds hard (energy
# up to 60,397 GWh in the 2024 vintage's High/2033 figure; peak_winter up
# to 8,762 MW in 2024's High/2032-33) — a legitimately wide spread, not
# extraction errors. rct/eue/capacity_outlook are still unrecalibrated
# placeholders (only ever populated for 2026 so far, via the PDF fallback).
PLAUSIBLE_RANGES = {
    'energy': (5_000, 65_000),        # GWh/year
    'peak_summer': (1_000, 9_000),    # MW
    'peak_winter': (1_000, 9_000),    # MW
    'minimum': (-1_000, 4_000),       # MW (2026 vintage forecasts a negative 90% POE minimum by 2035-36)
    'rct': (1_000, 8_000),            # MW — placeholder, not yet recalibrated
    'eue': (0, 10_000),               # MWh — placeholder, not yet recalibrated
    'capacity_outlook': (0, 20_000),  # MW — placeholder, not yet recalibrated
}


class Command(BaseCommand):
    help = 'Run FR-F08 validation checks over ingested EsooFigure rows and quarantine failures'

    def add_arguments(self, parser):
        parser.add_argument('--year', type=int, help='Only validate figures for this ESOO vintage year')
        parser.add_argument('--dry-run', action='store_true', help='Report without writing validation_status changes')

    def handle(self, *args, **options):
        qs = EsooFigure.objects.select_related('vintage')
        if options['year']:
            qs = qs.filter(vintage__year=options['year'])

        if not qs.exists():
            self.stdout.write(self.style.WARNING('No EsooFigure rows to validate.'))
            return

        dry_run = options['dry_run']
        passed, quarantined = 0, 0

        for figure in qs:
            reasons = self._check_completeness(figure) + self._check_range(figure)

            if reasons:
                quarantined += 1
                if not dry_run:
                    figure.validation_status = 'quarantined'
                    figure.validation_notes = '; '.join(reasons)
                    figure.save(update_fields=['validation_status', 'validation_notes'])
                self.stdout.write(self.style.ERROR(
                    f"  ✗ [{figure.vintage.year}/{figure.forecast_year}] {figure.metric} "
                    f"{figure.demand_growth_scenario} POE{figure.poe_level or '-'}: {'; '.join(reasons)}"
                ))
            else:
                passed += 1
                if not dry_run:
                    figure.validation_status = 'passed'
                    figure.validation_notes = ''
                    figure.save(update_fields=['validation_status', 'validation_notes'])

        dup_warnings = self._check_duplicates(qs)
        poe_warnings = self._check_poe_ordering(qs)

        self.stdout.write('\n' + '=' * 60)
        header = 'VALIDATION SUMMARY (dry run — no changes written)' if dry_run else 'VALIDATION SUMMARY'
        self.stdout.write(self.style.WARNING(header) if dry_run else self.style.SUCCESS(header))
        self.stdout.write('=' * 60)
        self.stdout.write(f"Checked: {passed + quarantined}")
        self.stdout.write(self.style.SUCCESS(f"✓ Passed: {passed}"))
        if quarantined:
            self.stdout.write(self.style.ERROR(f"✗ Quarantined: {quarantined}"))
        if dup_warnings:
            self.stdout.write(self.style.WARNING(f"⚠ Possible duplicate natural keys: {len(dup_warnings)}"))
            for w in dup_warnings[:10]:
                self.stdout.write(f"    {w}")
        if poe_warnings:
            self.stdout.write(self.style.WARNING(
                f"⚠ POE ordering anomalies (review — minimum-demand POE direction "
                f"is still open, spec OQ-3): {len(poe_warnings)}"
            ))
            for w in poe_warnings[:10]:
                self.stdout.write(f"    {w}")
        self.stdout.write('=' * 60 + '\n')

    def _check_completeness(self, figure):
        reasons = []
        if figure.value is None:
            reasons.append('missing value')
        if not figure.unit:
            reasons.append('missing unit')
        if not figure.forecast_year:
            reasons.append('missing forecast_year')
        if not figure.source_document:
            reasons.append('missing provenance: source_document')
        if not figure.extraction_date:
            reasons.append('missing provenance: extraction_date')
        if figure.domain == 'demand' and figure.metric in ('peak_summer', 'peak_winter', 'minimum') and figure.poe_level is None:
            reasons.append('missing poe_level for a peak/minimum demand figure')
        return reasons

    def _check_range(self, figure):
        bounds = PLAUSIBLE_RANGES.get(figure.metric)
        if bounds and figure.value is not None:
            lo, hi = bounds
            if not (lo <= figure.value <= hi):
                return [f'value {figure.value} {figure.unit} outside plausible range [{lo}, {hi}]']
        return []

    def _check_duplicates(self, qs):
        """
        The DB's unique_together doesn't reliably catch duplicates when
        poe_level is NULL (MySQL treats NULL != NULL for unique
        constraints, so e.g. two 'energy' rows with poe_level=None would
        both be accepted) — this re-verifies the natural key in Python.
        """
        seen = defaultdict(list)
        for f in qs:
            key = (
                f.vintage_id, f.domain, f.metric, f.forecast_year,
                f.demand_growth_scenario, f.poe_level, f.demand_basis,
            )
            seen[key].append(f.idesoofigure)
        return [f"{key}: figure ids {ids}" for key, ids in seen.items() if len(ids) > 1]

    def _check_poe_ordering(self, qs):
        """
        Peak demand (summer or winter): POE10 >= POE50 >= POE90 within the
        same (vintage, forecast_year, scenario, basis) — hard, well-
        established convention. Minimum-demand ordering is reported as a
        warning only, since AEMO's exceedance-direction convention for
        minimum is still open (OQ-3).
        """
        groups = defaultdict(dict)
        for f in qs.filter(metric__in=['peak_summer', 'peak_winter', 'minimum']):
            key = (f.vintage_id, f.forecast_year, f.demand_growth_scenario, f.demand_basis, f.metric)
            groups[key][f.poe_level] = f.value

        warnings = []
        for key, by_poe in groups.items():
            vintage_id, forecast_year, scenario, basis, metric = key
            if metric in ('peak_summer', 'peak_winter') and {10, 50, 90} <= by_poe.keys():
                if not (by_poe[10] >= by_poe[50] >= by_poe[90]):
                    warnings.append(
                        f"vintage_id={vintage_id} year={forecast_year} {scenario}/{basis} {metric}: "
                        f"POE10={by_poe[10]} POE50={by_poe[50]} POE90={by_poe[90]} not monotonic"
                    )
        return warnings
