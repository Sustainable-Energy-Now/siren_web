# siren_web/management/commands/sync_wind_capacities.py
from django.core.management.base import BaseCommand
from powermapui.signals import sync_wind_facility_capacities
from siren_web.models import facilities

class Command(BaseCommand):
    help = 'Sync wind facility capacities with their wind turbine totals'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making changes',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed output for each facility',
        )

    def handle(self, *args, **options):
        if options['dry_run']:
            self.stdout.write(
                self.style.WARNING('DRY RUN: No changes will be made')
            )
            self._dry_run_report(options['verbose'])
            return

        self.stdout.write('Starting wind facility capacity sync...')
        
        try:
            updated_count = sync_wind_facility_capacities()
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully updated {updated_count} wind facilities'
                )
            )
            
            if options['verbose']:
                self._show_wind_facilities_summary()
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error during sync: {str(e)}')
            )
            raise

    def _dry_run_report(self, verbose=False):
        """Show what would be updated in dry run mode"""
        wind_facilities = facilities.objects.filter(
            idtechnologies__technology_name__icontains='wind'
        ).prefetch_related('facilitywindturbines_set__idwindturbines')
        
        changes_count = 0
        
        for facility in wind_facilities:
            total_wind_capacity = facility.get_total_wind_capacity()
            
            if total_wind_capacity != facility.capacity:
                changes_count += 1
                if verbose:
                    self.stdout.write(
                        f"Would update {facility.facility_name}: "
                        f"{facility.capacity} -> {total_wind_capacity} MW"
                    )
        
        self.stdout.write(f"Would update {changes_count} facilities")

    def _show_wind_facilities_summary(self):
        """Show summary of all wind facilities"""
        wind_facilities = facilities.objects.filter(
            idtechnologies__technology_name__icontains='wind'
        ).prefetch_related('facilitywindturbines_set__idwindturbines')
        
        self.stdout.write("\nWind Facilities Summary:")
        self.stdout.write("-" * 50)
        
        for facility in wind_facilities:
            turbine_count = sum(
                inst.no_turbines for inst in 
                facility.facilitywindturbines_set.filter(is_active=True) # type: ignore
            )
            self.stdout.write(
                f"{facility.facility_name}: {facility.capacity} MW "
                f"({turbine_count} turbines)"
            )