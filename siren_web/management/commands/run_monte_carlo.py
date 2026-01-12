"""
Django management command to run Monte Carlo simulations for renewable energy targets.

Usage:
    python manage.py run_monte_carlo --all
    python manage.py run_monte_carlo --scenario-id 1
    python manage.py run_monte_carlo --scenario-name "Base Case" --iterations 10000

Scheduled via cron:
    0 2 1 * * cd /path/to/siren_web && python manage.py run_monte_carlo --all >> /var/log/monte_carlo.log 2>&1
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Run Monte Carlo simulation for renewable energy target scenarios'

    def add_arguments(self, parser):
        """Define command-line arguments."""
        # Scenario selection (mutually exclusive)
        scenario_group = parser.add_mutually_exclusive_group(required=True)
        scenario_group.add_argument(
            '--scenario-id',
            type=int,
            help='Run simulation for specific scenario ID'
        )
        scenario_group.add_argument(
            '--all',
            action='store_true',
            help='Run simulation for all active scenarios'
        )

        # Scenario selection by type and year
        parser.add_argument(
            '--scenario-type',
            type=str,
            help='Scenario type (base_case, delayed_pipeline, accelerated_pipeline)'
        )
        parser.add_argument(
            '--year',
            type=int,
            help='Target year for the scenario'
        )

        # Simulation parameters
        parser.add_argument(
            '--iterations',
            type=int,
            default=100000,
            help='Number of Monte Carlo iterations (default: 100000)'
        )
        parser.add_argument(
            '--profile',
            type=str,
            default='optimistic',
            choices=['optimistic', 'balanced', 'conservative'],
            help='Commissioning probability profile (default: optimistic)'
        )
        parser.add_argument(
            '--target-year',
            type=int,
            default=2040,
            help='Target year for projections (default: 2040)'
        )

        # Options
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force re-run even if recent simulation exists'
        )

    def handle(self, *args, **options):
        """Execute the command."""
        from siren_web.models import TargetScenario, MonteCarloSimulation
        from powerplotui.services.monte_carlo_simulator import MonteCarloSimulator

        # Extract options
        scenario_id = options.get('scenario_id')
        scenario_type = options.get('scenario_type')
        year = options.get('year')
        run_all = options.get('all')
        iterations = options['iterations']
        profile = options['profile']
        target_year = options['target_year']
        force = options.get('force', False)

        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('Monte Carlo Simulation for Renewable Energy Targets'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(f"Iterations: {iterations:,}")
        self.stdout.write(f"Profile: {profile}")
        self.stdout.write(f"Target Year: {target_year}")
        self.stdout.write('')

        # Get scenarios to process
        scenarios = self._get_scenarios(scenario_id, scenario_type, year, run_all)

        if not scenarios:
            raise CommandError("No scenarios found to process")

        self.stdout.write(f"Found {len(scenarios)} scenario(s) to process:")
        for scenario in scenarios:
            self.stdout.write(f"  - {scenario.display_name}")
        self.stdout.write('')

        # Process each scenario
        results = []
        for idx, scenario in enumerate(scenarios, 1):
            self.stdout.write(self.style.HTTP_INFO(f"[{idx}/{len(scenarios)}] Processing: {scenario.display_name}"))

            try:
                # Check if recent simulation exists
                if not force:
                    recent_run = MonteCarloSimulation.objects.filter(
                        target_scenario=scenario,
                        status='completed'
                    ).order_by('-run_date').first()

                    if recent_run:
                        days_ago = (timezone.now() - recent_run.run_date).days
                        if days_ago < 30:  # Less than 30 days old
                            self.stdout.write(self.style.WARNING(
                                f"  Recent simulation exists ({days_ago} days ago). "
                                f"Skipping. Use --force to override."
                            ))
                            continue

                # Create simulation record
                simulation = MonteCarloSimulation.objects.create(
                    target_scenario=scenario,
                    num_iterations=iterations,
                    target_year=target_year,
                    probability_profile=profile,
                    status='pending',
                    created_by='management_command'
                )

                self.stdout.write(f"  Created simulation record ID {simulation.simulation_id}")

                # Run simulation
                simulator = MonteCarloSimulator(
                    target_scenario=scenario,
                    num_iterations=iterations,
                    probability_profile=profile,
                    target_year=target_year
                )

                simulation = simulator.run_simulation(simulation)

                # Report results
                self.stdout.write(self.style.SUCCESS(f"  ✓ Completed in {simulation.execution_time_seconds:.1f}s"))
                self.stdout.write(f"    Mean RE%: {simulation.mean_re_percentage:.2f}%")
                self.stdout.write(f"    90% CI: [{simulation.p10_re_percentage:.2f}%, {simulation.p90_re_percentage:.2f}%]")
                self.stdout.write(f"    P(75% target): {simulation.probability_75_percent:.1f}%")
                self.stdout.write(f"    P(85% target): {simulation.probability_85_percent:.1f}%")

                results.append({
                    'scenario': scenario.display_name,
                    'simulation_id': simulation.simulation_id,
                    'status': 'success',
                    'prob_85': simulation.probability_85_percent,
                })

            except Exception as e:
                self.stderr.write(self.style.ERROR(f"  ✗ Failed: {str(e)}"))
                logger.error(f"Monte Carlo failed for scenario {scenario.id}: {e}", exc_info=True)

                results.append({
                    'scenario': scenario.display_name,
                    'status': 'failed',
                    'error': str(e),
                })

            self.stdout.write('')  # Blank line between scenarios

        # Summary
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('Summary'))
        self.stdout.write(self.style.SUCCESS('=' * 70))

        success_count = sum(1 for r in results if r['status'] == 'success')
        failed_count = sum(1 for r in results if r['status'] == 'failed')

        self.stdout.write(f"Total scenarios: {len(results)}")
        self.stdout.write(self.style.SUCCESS(f"Successful: {success_count}"))
        if failed_count > 0:
            self.stdout.write(self.style.ERROR(f"Failed: {failed_count}"))

        # List results
        if success_count > 0:
            self.stdout.write('')
            self.stdout.write("Results:")
            for result in results:
                if result['status'] == 'success':
                    self.stdout.write(
                        f"  {result['scenario']}: "
                        f"P(85%) = {result['prob_85']:.1f}% "
                        f"(Simulation #{result['simulation_id']})"
                    )

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('Done!'))

    def _get_scenarios(self, scenario_id, scenario_type, year, run_all):
        """
        Get list of scenarios to process based on arguments.

        Args:
            scenario_id: int or None
            scenario_type: str or None
            year: int or None
            run_all: bool

        Returns:
            List of TargetScenario instances
        """
        from siren_web.models import TargetScenario

        if run_all:
            # Get all active scenarios
            scenarios = TargetScenario.objects.filter(is_active=True)
            return list(scenarios)

        elif scenario_id:
            # Get specific scenario by ID
            try:
                scenario = TargetScenario.objects.get(pk=scenario_id)
                return [scenario]
            except TargetScenario.DoesNotExist:
                raise CommandError(f"Scenario with ID {scenario_id} not found")

        elif scenario_type and year:
            # Get scenario by type and year (unique_together constraint)
            try:
                scenario = TargetScenario.objects.get(
                    scenario_type=scenario_type,
                    year=year
                )
                return [scenario]
            except TargetScenario.DoesNotExist:
                raise CommandError(
                    f"Scenario with type '{scenario_type}' and year {year} not found"
                )

        return []