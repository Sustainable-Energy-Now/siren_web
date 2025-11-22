# scripts/initialize_re_targets.py
"""
Script to initialize renewable energy targets and scenarios
Run once to set up the baseline data
"""

from django.core.management.base import BaseCommand
from siren_web.models import RenewableEnergyTarget, TargetScenario


class Command(BaseCommand):
    help = 'Initialize renewable energy targets and scenarios'

    def handle(self, *args, **options):
        self.stdout.write('Initializing RE targets and scenarios...')
        
        # Create main targets
        targets = [
            {
                'target_year': 2024,
                'target_percentage': 37.5,
                'target_emissions_tonnes': 8500000,
                'description': '2024 interim target',
                'is_interim_target': True
            },
            {
                'target_year': 2025,
                'target_percentage': 40.0,
                'target_emissions_tonnes': 7900000,
                'description': '2025 interim target',
                'is_interim_target': True
            },
            {
                'target_year': 2027,
                'target_percentage': 57.0,
                'target_emissions_tonnes': 5400000,
                'description': '2027 interim target',
                'is_interim_target': True
            },
            {
                'target_year': 2028,
                'target_percentage': 65.0,
                'target_emissions_tonnes': 4800000,
                'description': '2028 interim target',
                'is_interim_target': True
            },
            {
                'target_year': 2040,
                'target_percentage': 75.0,
                'target_emissions_tonnes': 4200000,
                'description': 'SWIS 2040 renewable energy target',
                'is_interim_target': False
            },
        ]
        
        for target_data in targets:
            target, created = RenewableEnergyTarget.objects.update_or_create(
                target_year=target_data['target_year'],
                defaults=target_data
            )
            
            if created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  Created target: {target.target_year} - {target.target_percentage}%"
                    )
                )
            else:
                self.stdout.write(
                    f"  Updated target: {target.target_year} - {target.target_percentage}%"
                )
        
        # Create scenarios
        scenarios = [
            {
                'scenario_name': 'Base Case (Planned + Probable)',
                'scenario_type': 'base_case',
                'description': '''Base case assumes all Planned and Probable facilities are commissioned 
                                 on schedule with expected capacity factors and normal demand growth.''',
                'projected_re_percentage_2040': 76.8,
                'projected_emissions_2040_tonnes': 3890000,
                'wind_generation_2040': 9247,
                'solar_utility_generation_2040': 4187,
                'solar_rooftop_generation_2040': 3413,
                'biomass_hydro_generation_2040': 547,
                'gas_ccgt_generation_2040': 4789,
                'gas_ocgt_generation_2040': 767,
                'probability_percentage': 78.0,
                'is_active': True
            },
            {
                'scenario_name': 'High Electrification',
                'scenario_type': 'high_electrification',
                'description': '''Assumes accelerated electrification of transport and industry, 
                                 increasing demand by 15% above base case.''',
                'projected_re_percentage_2040': 68.5,
                'projected_emissions_2040_tonnes': 5200000,
                'wind_generation_2040': 9247,
                'solar_utility_generation_2040': 4187,
                'solar_rooftop_generation_2040': 3900,  # Higher rooftop adoption
                'biomass_hydro_generation_2040': 547,
                'gas_ccgt_generation_2040': 6500,  # More gas needed
                'gas_ocgt_generation_2040': 1200,
                'probability_percentage': 35.0,
                'is_active': True
            },
            {
                'scenario_name': 'Delayed Pipeline',
                'scenario_type': 'delayed_pipeline',
                'description': '''Assumes 20% of Probable facilities are delayed beyond 2040 
                                 due to supply chain, permitting, or financing issues.''',
                'projected_re_percentage_2040': 71.2,
                'projected_emissions_2040_tonnes': 4850000,
                'wind_generation_2040': 7800,  # Reduced from delays
                'solar_utility_generation_2040': 3600,  # Reduced from delays
                'solar_rooftop_generation_2040': 3413,
                'biomass_hydro_generation_2040': 547,
                'gas_ccgt_generation_2040': 5600,
                'gas_ocgt_generation_2040': 950,
                'probability_percentage': 22.0,
                'is_active': True
            },
            {
                'scenario_name': 'Accelerated Pipeline',
                'scenario_type': 'accelerated_pipeline',
                'description': '''Assumes 50% of Possible facilities advance to Probable/Planned 
                                 status and commission by 2040.''',
                'projected_re_percentage_2040': 82.3,
                'projected_emissions_2040_tonnes': 3100000,
                'wind_generation_2040': 11200,
                'solar_utility_generation_2040': 5400,
                'solar_rooftop_generation_2040': 3413,
                'biomass_hydro_generation_2040': 547,
                'gas_ccgt_generation_2040': 3800,
                'gas_ocgt_generation_2040': 450,
                'probability_percentage': 45.0,
                'is_active': True
            },
        ]
        
        for scenario_data in scenarios:
            scenario, created = TargetScenario.objects.update_or_create(
                scenario_name=scenario_data['scenario_name'],
                defaults=scenario_data
            )
            
            if created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  Created scenario: {scenario.scenario_name} - "
                        f"{scenario.projected_re_percentage_2040}% by 2040"
                    )
                )
            else:
                self.stdout.write(
                    f"  Updated scenario: {scenario.scenario_name}"
                )
        
        self.stdout.write(
            self.style.SUCCESS(
                '\nSuccessfully initialized RE targets and scenarios!'
            )
        )
        
        # Print summary
        self.stdout.write('\n' + '='*60)
        self.stdout.write('Summary:')
        self.stdout.write('='*60)
        
        for target in RenewableEnergyTarget.objects.all().order_by('target_year'):
            marker = "→" if target.is_interim_target else "★"
            self.stdout.write(
                f"{marker} {target.target_year}: {target.target_percentage}% RE "
                f"({target.target_emissions_tonnes/1000000:.1f}M tonnes CO₂-e)"
            )
        
        self.stdout.write('\nBase Case Scenario:')
        base = TargetScenario.objects.filter(scenario_type='base_case').first()
        if base:
            self.stdout.write(
                f"  2040 Projection: {base.projected_re_percentage_2040}% RE "
                f"({base.probability_percentage}% probability)"
            )
            target_2040 = RenewableEnergyTarget.objects.get(target_year=2040)
            gap = base.projected_re_percentage_2040 - target_2040.target_percentage
            status = "✓ EXCEEDS" if gap >= 0 else "✗ BELOW"
            self.stdout.write(
                f"  Status: {status} 2040 target by {abs(gap):.1f} percentage points"
            )