"""
Analyses one full calendar year of FacilityScadaMatrix per facility and
writes the observed results back onto the existing model fields:
FacilityGenerators.capacity_max/capacity_min, Storageattributes.
round_trip_efficiency (skipped when the technology is shared by more than
one active storage installation), and facilities.capacityfactor.

See siren_web/services/facility_capacity_analyzer.py for the analysis and
write-back logic; this command is a thin CLI/pipeline wrapper around it.
"""
from django.core.management.base import BaseCommand

from siren_web.services.facility_capacity_analyzer import (
    MIN_COVERAGE_DEFAULT,
    analyze_year,
    apply_results,
    get_latest_full_scada_year,
)


class Command(BaseCommand):
    help = (
        'Derive facility capacity_max/capacity_min, round-trip efficiency and capacity factor '
        'from a full calendar year of FacilityScadaMatrix, and write them onto the existing fields.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--year', type=int,
            help='Calendar year to analyze. Default: the latest full year of SCADA data.',
        )
        parser.add_argument(
            '--min-coverage', type=float, default=MIN_COVERAGE_DEFAULT,
            help=f'Minimum fraction (0-1) of non-missing half-hourly intervals required (default: {MIN_COVERAGE_DEFAULT}).',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Analyze and print results without writing anything.',
        )

    def handle(self, *args, **options):
        year = options['year']
        if not year:
            year = get_latest_full_scada_year()
            self.stdout.write(f'No --year given; using latest full year: {year}')

        min_coverage = options['min_coverage']
        results = analyze_year(year, min_coverage=min_coverage)

        if not results:
            self.stdout.write(self.style.ERROR(f'No facilities found in FacilityScadaMatrix for {year}.'))
            return

        for result in results:
            if result.skip_reason:
                self.stdout.write(self.style.WARNING(
                    f'  [{result.facility_id}] {result.facility_name}: skipped -- {result.skip_reason}'
                ))
                continue
            parts = [f'coverage {result.coverage:.1%}']
            if result.max_mw is not None:
                parts.append(f'max {result.max_mw:.1f} MW')
            if result.min_mw is not None:
                parts.append(f'min {result.min_mw:.1f} MW')
            if result.capacity_factor is not None:
                parts.append(f'CF {result.capacity_factor:.1%}')
            if result.round_trip_efficiency is not None:
                parts.append(f'RTE {result.round_trip_efficiency:.1%}')
            self.stdout.write(f'  [{result.facility_id}] {result.facility_name}: ' + ', '.join(parts))

        summary = apply_results(results, dry_run=options['dry_run'])
        verb = 'Would apply' if options['dry_run'] else 'Applied'
        self.stdout.write(self.style.SUCCESS(
            f"{year}: {summary['analyzed']} analyzed, {verb.lower()} to {summary['applied']}, "
            f"{summary['skipped']} skipped."
        ))
