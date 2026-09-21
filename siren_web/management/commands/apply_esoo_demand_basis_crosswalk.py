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

from siren_web.models import EsooFigure
from powerplotui.services.esoo_demand_basis_crosswalk import (
    CrosswalkSkipped,
    DemandBasisCrosswalk,
    derive_operational_energy_figure,
)

IDENTITY_FIELDS = {
    'vintage', 'domain', 'metric', 'forecast_year',
    'demand_growth_scenario', 'poe_level', 'demand_basis',
}


class Command(BaseCommand):
    help = (
        "Derive operational-basis energy figures from published underlying-basis ones "
        "(FR-F07, D13): (underlying - DPV behind-the-meter) x operational/delivered factor, "
        "both taken from AEMO's own published Expected-scenario consumption components. "
        "Never extrapolates past a vintage's published horizon and never overwrites a "
        "figure AEMO published directly. Derived rows are always recomputed."
    )

    def add_arguments(self, parser):
        parser.add_argument('--year', type=int, help='Restrict to one ESOO vintage year')
        parser.add_argument('--dry-run', action='store_true', help='Report what would be written without writing it')

    def handle(self, *args, **options):
        qs = EsooFigure.objects.filter(domain='demand', metric='energy', demand_basis='underlying')
        if options['year']:
            qs = qs.filter(vintage__year=options['year'])
        underlying_figures = list(qs.select_related('vintage').order_by('vintage__year', 'forecast_year', 'demand_growth_scenario'))

        if not underlying_figures:
            self.stdout.write(self.style.WARNING('No underlying-basis energy figures found for the given filter.'))
            return

        self.stdout.write(f'Found {len(underlying_figures)} underlying-basis energy figure(s) to consider.')

        crosswalk = DemandBasisCrosswalk()
        derived, skipped, unchanged = 0, 0, 0
        skip_reasons = {}

        for fig in underlying_figures:
            existing = EsooFigure.objects.filter(
                vintage=fig.vintage, domain=fig.domain, metric=fig.metric,
                forecast_year=fig.forecast_year, demand_growth_scenario=fig.demand_growth_scenario,
                poe_level=fig.poe_level, demand_basis='operational',
            ).first()
            if existing and existing.extraction_method != 'dpv_subtraction':
                # A directly-published operational figure already exists for this
                # key -- never overwrite it with a derived one (D3's default wins
                # wherever AEMO actually published the real thing).
                unchanged += 1
                continue

            try:
                defaults = derive_operational_energy_figure(fig, crosswalk=crosswalk)
            except CrosswalkSkipped as e:
                # Report the first skip per vintage only; the reason is the same for the rest.
                if fig.vintage.year not in skip_reasons:
                    skip_reasons[fig.vintage.year] = str(e)
                    self.stdout.write(self.style.WARNING(f"  SKIP {fig.vintage.year} -> {fig.forecast_year} {fig.demand_growth_scenario}: {e}"))
                skipped += 1
                continue

            if options['dry_run']:
                self.stdout.write(
                    f"  [dry-run] {fig.vintage.year} -> {fig.forecast_year} {fig.demand_growth_scenario}: "
                    f"{fig.value:,.2f} GWh (underlying) -> {defaults['value']:,.2f} GWh (derived operational)"
                )
                derived += 1
                continue

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
            self.stdout.write(self.style.WARNING(f'Dry run -- {derived} would be derived, {skipped} skipped, {unchanged} published (left as is).'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Done -- {derived} derived, {skipped} skipped, {unchanged} published (left as is).'))
