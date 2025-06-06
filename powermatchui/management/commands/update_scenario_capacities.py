# management/commands/update_scenario_capacities.py
from django.core.management.base import BaseCommand
from django.db import transaction
from siren_web.models import ScenariosTechnologies, Technologies, facilities

class Command(BaseCommand):
    help = 'Update all ScenariosTechnologies capacity fields from facilities'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clean-orphans',
            action='store_true',
            help='Remove orphaned ScenariosTechnologies records that reference non-existent Technologies',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        clean_orphans = options['clean_orphans']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
        
        # First, handle orphaned records
        if clean_orphans:
            self.clean_orphaned_records(dry_run)
        
        # Then update capacities
        self.update_capacities(dry_run)

    def clean_orphaned_records(self, dry_run=False):
        """Remove ScenariosTechnologies records that reference non-existent Technologies"""
        self.stdout.write('Checking for orphaned ScenariosTechnologies records...')
        
        # Find ScenariosTechnologies with invalid technology references
        orphaned_records = []
        
        for scenario_tech in ScenariosTechnologies.objects.all():
            try:
                # Try to access the technology - this will raise DoesNotExist if orphaned
                _ = scenario_tech.idtechnologies
            except Technologies.DoesNotExist:
                orphaned_records.append(scenario_tech)
        
        if orphaned_records:
            self.stdout.write(
                self.style.WARNING(f'Found {len(orphaned_records)} orphaned ScenariosTechnologies records')
            )
            
            for record in orphaned_records:
                self.stdout.write(f'  - ScenariosTechnologies ID {record.idscenariostechnologies} (references missing technology)')
            
            if not dry_run:
                with transaction.atomic():
                    for record in orphaned_records:
                        record.delete()
                self.stdout.write(
                    self.style.SUCCESS(f'Deleted {len(orphaned_records)} orphaned records')
                )
            else:
                self.stdout.write('Would delete these orphaned records (use --clean-orphans without --dry-run)')
        else:
            self.stdout.write(self.style.SUCCESS('No orphaned records found'))

    def update_capacities(self, dry_run=False):
        """Update capacity for valid ScenariosTechnologies records"""
        self.stdout.write('Updating ScenariosTechnologies capacities...')
        
        updated_count = 0
        error_count = 0
        
        # Only process records with valid technology references
        valid_scenario_techs = ScenariosTechnologies.objects.select_related('idtechnologies', 'idscenarios')
        
        for scenario_tech in valid_scenario_techs:
            try:
                old_capacity = scenario_tech.capacity
                
                if dry_run:
                    # Calculate what the new capacity would be without saving
                    total_capacity = facilities.objects.filter(
                        idtechnologies=scenario_tech.idtechnologies,
                        scenariosfacilities__idscenarios=scenario_tech.idscenarios
                    ).aggregate(total=models.Sum('capacity'))['total'] or 0
                    new_capacity = total_capacity
                else:
                    new_capacity = scenario_tech.update_capacity()
                
                if old_capacity != new_capacity:
                    scenario_name = scenario_tech.idscenarios.title if scenario_tech.idscenarios else 'Unknown'
                    tech_name = scenario_tech.idtechnologies.technology_name if scenario_tech.idtechnologies else 'Unknown'
                    
                    if dry_run:
                        self.stdout.write(
                            f'Would update {scenario_name} - {tech_name}: {old_capacity} -> {new_capacity}'
                        )
                    else:
                        self.stdout.write(
                            f'Updated {scenario_name} - {tech_name}: {old_capacity} -> {new_capacity}'
                        )
                    updated_count += 1
                    
            except Exception as e:
                error_count += 1
                self.stdout.write(
                    self.style.ERROR(f'Error updating ScenariosTechnologies ID {scenario_tech.idscenariostechnologies}: {e}')
                )
        
        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(f'Would update {updated_count} records. {error_count} errors encountered.')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'Updated {updated_count} records. {error_count} errors encountered.')
            )

    def get_capacity_summary(self):
        """Display a summary of current capacity data"""
        total_scenario_techs = ScenariosTechnologies.objects.count()
        scenario_techs_with_capacity = ScenariosTechnologies.objects.filter(capacity__isnull=False).count()
        
        self.stdout.write(f'Total ScenariosTechnologies records: {total_scenario_techs}')
        self.stdout.write(f'Records with capacity values: {scenario_techs_with_capacity}')
        self.stdout.write(f'Records without capacity: {total_scenario_techs - scenario_techs_with_capacity}')