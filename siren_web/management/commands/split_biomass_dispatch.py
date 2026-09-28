"""
Sets the Biomass Technologies row to non-dispatchable and moves any facility
with zero qualifying SCADA-trace years onto a new "Biomass (dispatchable)"
twin technology, so it keeps the old nameplate-optimized dispatch behavior
instead of silently contributing zero generation.

Run build_biomass_supply_traces first, with the same --min-coverage, so the
qualifying facilities already have a real trace in SupplyFactorMatrix before
this flips the dispatch flag -- see siren_web/services/biomass_dispatch_split.py.
"""
from django.core.management.base import BaseCommand, CommandError

from siren_web.services.biomass_dispatch_split import (
    MIN_COVERAGE_DEFAULT,
    TRACE_YEARS,
    apply_plan,
    build_plan,
)


class Command(BaseCommand):
    help = (
        'Set Biomass to non-dispatchable and move any facility without a real SCADA '
        'trace onto a dispatchable twin technology.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--min-coverage', type=float, default=MIN_COVERAGE_DEFAULT,
            help='Must match the --min-coverage used by build_biomass_supply_traces '
                 f'(default: {MIN_COVERAGE_DEFAULT}).',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Print the plan without writing anything.',
        )

    def handle(self, *args, **options):
        try:
            plan = build_plan(min_coverage=options['min_coverage'], years=TRACE_YEARS)
        except ValueError as exc:
            raise CommandError(str(exc))

        self.stdout.write(
            f'Source technology: {plan.source_technology.technology_name} '
            f'(id={plan.source_technology.idtechnologies}, '
            f'dispatchable={plan.source_technology.dispatchable})'
        )
        self.stdout.write(f'Staying on Biomass (non-dispatchable): {len(plan.facilities_staying)} facilities')
        for result in plan.facilities_staying:
            self.stdout.write(
                f'  [{result.facility_id}] {result.facility_name}: qualifying years {result.qualifying_years}'
            )
        self.stdout.write(f'Moving to dispatchable twin: {len(plan.facilities_to_repoint)} facilities')
        for result in plan.facilities_to_repoint:
            self.stdout.write(f'  [{result.facility_id}] {result.facility_name}')

        dry_run = options['dry_run']
        summary = apply_plan(plan, dry_run=dry_run)

        verb = 'Would' if dry_run else 'Did'
        if summary['twin_technology_name']:
            self.stdout.write(
                f"{verb} use twin technology '{summary['twin_technology_name']}' "
                f"({'newly created' if summary['twin_created'] else 'existing'})."
            )
            for change in summary['facilities_repointed']:
                self.stdout.write(
                    f"  [{change['facility_id']}] {change['facility_name']}: "
                    f"{verb.lower()} move {change['facility_generators_moved']} FacilityGenerators row(s), "
                    f"create {change['scenarios_technologies_created']} ScenariosTechnologies row(s)."
                )
        if summary['source_set_non_dispatchable']:
            self.stdout.write(self.style.SUCCESS(
                f"{verb} set {plan.source_technology.technology_name}.dispatchable = 0."
            ))
        else:
            self.stdout.write(self.style.WARNING(
                'No facilities are staying on Biomass with a real trace -- dispatchable flag left untouched.'
            ))

        if dry_run:
            self.stdout.write(self.style.WARNING('Dry run -- no changes written. Re-run without --dry-run to apply.'))

        self.stdout.write(
            "Note: a dispatch run only picks up these traces for a scenario if the Demand "
            "forecast selected for that run has a reference_year of 2024 or 2025 recorded -- "
            "see resolve_baseline_year in siren_web/database_operations.py."
        )
