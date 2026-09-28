"""
Builds real hourly generation traces for Biomass facilities from their own
FacilityScadaMatrix SCADA history (2024/2025) and writes them into
SupplyFactorMatrix, so the dispatch engine can use them as fixed
non-dispatchable input instead of economically optimizing biomass output.

See siren_web/services/biomass_trace_from_scada.py for the analysis/write
logic; this command is a thin CLI/pipeline wrapper. Run split_biomass_dispatch
next to flip Technologies.dispatchable and move any facility with zero
qualifying years onto a dispatchable twin technology.
"""
from django.core.management.base import BaseCommand

from siren_web.services.biomass_trace_from_scada import (
    HOURS_PER_YEAR,
    MIN_COVERAGE_DEFAULT,
    TRACE_YEARS,
    analyze,
    build_traces,
)


class Command(BaseCommand):
    help = (
        'Build real hourly Biomass generation traces from FacilityScadaMatrix '
        '(2024/2025) and write them into SupplyFactorMatrix.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--min-coverage', type=float, default=MIN_COVERAGE_DEFAULT,
            help='Minimum fraction (0-1) of non-missing half-hourly intervals required, '
                 f'per year (default: {MIN_COVERAGE_DEFAULT}).',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Analyze and print results without writing anything.',
        )

    def handle(self, *args, **options):
        min_coverage = options['min_coverage']
        results = analyze(min_coverage=min_coverage, years=TRACE_YEARS)

        if not results:
            self.stdout.write(self.style.ERROR('No Biomass facilities found.'))
            return

        for result in results:
            coverage_str = ', '.join(
                f'{year}={result.coverage_by_year[year]:.1%}' for year in TRACE_YEARS
            )
            if result.moves_to_twin:
                self.stdout.write(self.style.WARNING(
                    f'  [{result.facility_id}] {result.facility_name}: {coverage_str} '
                    '-> NO qualifying year, will move to dispatchable twin technology'
                ))
            else:
                qualifying = ', '.join(str(y) for y in result.qualifying_years)
                self.stdout.write(
                    f'  [{result.facility_id}] {result.facility_name}: {coverage_str} '
                    f'-> trace will be built for {qualifying}'
                )

        summary = build_traces(results, dry_run=options['dry_run'])

        for result in summary['results']:
            for year in result.dropped_leap_day:
                self.stdout.write(self.style.WARNING(
                    f'  [{result.facility_id}] {result.facility_name}: dropped 29 Feb {year} '
                    f'to keep the trace at {HOURS_PER_YEAR} hours.'
                ))

        verb = 'Would build' if options['dry_run'] else 'Built'
        self.stdout.write(self.style.SUCCESS(
            f"{verb} traces for {summary['facilities_with_trace']} facilities; "
            f"{summary['facilities_to_twin']} have no qualifying year and need "
            "split_biomass_dispatch to move them onto a dispatchable twin technology."
        ))
        self.stdout.write(
            "Note: a dispatch run only picks up these traces for a scenario if the Demand "
            "forecast selected for that run has a reference_year of 2024 or 2025 recorded -- "
            "see resolve_baseline_year in siren_web/database_operations.py."
        )
