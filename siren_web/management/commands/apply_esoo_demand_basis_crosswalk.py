# siren_web/management/commands/apply_esoo_demand_basis_crosswalk.py
"""
FR-F07 (D13) -- run the underlying-to-operational energy crosswalk across
ingested EsooFigure rows and write the derived operational-basis figures
alongside the originals.

WS1 task: this is a Foundation-level, post-processing step over already-
ingested figures (not a fresh extraction from source documents), so both
G1 (esoo_scenario_views.resolve_esoo_anchors) and G2
(esoo_bias_analysis.align_forecast_actual_pairs) pick up the derived rows
automatically -- neither queries anything beyond EsooFigure's normal
(vintage, metric, forecast_year, demand_basis) key, and neither needed any
code changes for this.
"""
from django.core.management.base import BaseCommand
from django.db import connection

from siren_web.models import EsooFigure
from powerplotui.services.esoo_demand_basis_crosswalk import (
    CrosswalkSkipped,
    DEFAULT_MIN_COVERAGE_PCT,
    derive_operational_energy_figure,
)


class Command(BaseCommand):
    help = (
        "Derive operational-basis energy figures from published underlying-basis ones "
        "(FR-F07, D13) wherever real DPVGeneration data adequately covers the target "
        "Capacity Year. Never fabricates a growth-projected estimate for years beyond "
        "DPV's real coverage -- those are skipped and reported, not guessed."
    )

    def add_arguments(self, parser):
        parser.add_argument('--year', type=int, help='Restrict to one ESOO vintage year')
        parser.add_argument(
            '--min-coverage', type=float, default=DEFAULT_MIN_COVERAGE_PCT,
            help=f'Minimum %% DPV interval coverage required for a Capacity Year before it is '
                 f'crosswalked (default: {DEFAULT_MIN_COVERAGE_PCT})',
        )
        parser.add_argument('--dry-run', action='store_true', help='Report what would be written without writing it')
        parser.add_argument('--force', action='store_true', help='Recompute even if a derived figure already exists')

    def handle(self, *args, **options):
        connection.close()  # DPV aggregation is a real DB scan; avoid a stale idle connection

        qs = EsooFigure.objects.filter(domain='demand', metric='energy', demand_basis='underlying')
        if options['year']:
            qs = qs.filter(vintage__year=options['year'])
        underlying_figures = list(qs.select_related('vintage').order_by('vintage__year', 'forecast_year', 'demand_growth_scenario'))

        if not underlying_figures:
            self.stdout.write(self.style.WARNING('No underlying-basis energy figures found for the given filter.'))
            return

        self.stdout.write(f'Found {len(underlying_figures)} underlying-basis energy figure(s) to consider.')

        derived, skipped, unchanged = 0, 0, 0
        min_coverage = options['min_coverage']

        for fig in underlying_figures:
            key = dict(
                vintage=fig.vintage, domain=fig.domain, metric=fig.metric,
                forecast_year=fig.forecast_year, demand_growth_scenario=fig.demand_growth_scenario,
                poe_level=fig.poe_level, demand_basis='operational',
            )
            existing = EsooFigure.objects.filter(**key).first()
            if existing and existing.extraction_method != 'dpv_subtraction':
                # A directly-published operational figure already exists for this
                # key -- never overwrite it with a derived one (D3's default wins
                # wherever AEMO actually published the real thing).
                unchanged += 1
                continue
            if existing and not options['force']:
                self.stdout.write(
                    f"  {fig.vintage.year} {fig.forecast_year} {fig.demand_growth_scenario}: "
                    f"already crosswalked. Use --force to recompute."
                )
                unchanged += 1
                continue

            try:
                defaults = derive_operational_energy_figure(fig, min_coverage_pct=min_coverage)
            except CrosswalkSkipped as e:
                self.stdout.write(self.style.WARNING(
                    f"  SKIP {fig.vintage.year} -> {fig.forecast_year} {fig.demand_growth_scenario}: {e}"
                ))
                skipped += 1
                continue

            if options['dry_run']:
                self.stdout.write(
                    f"  [dry-run] {fig.vintage.year} -> {fig.forecast_year} {fig.demand_growth_scenario}: "
                    f"{fig.value:,.2f} GWh (underlying) -> {defaults['value']:,.2f} GWh (derived operational)"
                )
                derived += 1
                continue

            IDENTITY_FIELDS = {
                'vintage', 'domain', 'metric', 'forecast_year',
                'demand_growth_scenario', 'poe_level', 'demand_basis',
            }
            update_fields = {k: v for k, v in defaults.items() if k not in IDENTITY_FIELDS}
            EsooFigure.objects.update_or_create(
                vintage=fig.vintage, domain=fig.domain, metric=fig.metric,
                forecast_year=fig.forecast_year, demand_growth_scenario=fig.demand_growth_scenario,
                poe_level=fig.poe_level, demand_basis='operational',
                defaults=update_fields,
            )
            self.stdout.write(self.style.SUCCESS(
                f"  {fig.vintage.year} -> {fig.forecast_year} {fig.demand_growth_scenario}: "
                f"{fig.value:,.2f} GWh (underlying) -> {defaults['value']:,.2f} GWh (derived operational)"
            ))
            derived += 1

        self.stdout.write('')
        if options['dry_run']:
            self.stdout.write(self.style.WARNING(f'Dry run -- {derived} would be derived, {skipped} skipped, {unchanged} unchanged.'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Done -- {derived} derived, {skipped} skipped (insufficient DPV coverage), {unchanged} unchanged.'))
