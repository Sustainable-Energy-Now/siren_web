# Create this file: siren_web/management/commands/load_components.py
# First create the directories if they don't exist:
# mkdir -p siren_web/management/commands

from django.core.management.base import BaseCommand
from django.db import transaction
from siren_web.models import SystemComponent, ComponentConnection

class Command(BaseCommand):
    help = 'Load initial system components and connections from your legacy setup'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing components before loading new ones',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be created without actually creating it',
        )
    
    def handle(self, *args, **options):
        if options['clear'] and not options['dry_run']:
            self.stdout.write('Clearing existing components...')
            ComponentConnection.objects.all().delete()
            SystemComponent.objects.all().delete()
        
        # Define your components based on the original image map coordinates
        # Converted coordinates from original (2605x1760) to new coordinate system (800x600)
        components_data = [
            # Database Models (from your original models mapping)
            {
                'name': 'Analysis',
                'display_name': 'Analysis',
                'component_type': 'model',
                'model_class_name': 'Analysis',
                'description': 'Analysis and reporting module for system performance evaluation',
                'position_x': 350,
                'position_y': 400,
                'width': 120,
                'height': 60,
            },
            {
                'name': 'Facilities',
                'display_name': 'Facilities',
                'component_type': 'model',
                'model_class_name': 'facilities',
                'description': 'Power generation facilities and infrastructure data',
                'position_x': 50,
                'position_y': 150,
                'width': 120,
                'height': 60,
            },
            {
                'name': 'Scenarios',
                'display_name': 'Scenarios',
                'component_type': 'model',
                'model_class_name': 'Scenarios',
                'description': 'Energy scenarios and planning configurations',
                'position_x': 50,
                'position_y': 250,
                'width': 120,
                'height': 60,
            },
            {
                'name': 'Technologies',
                'display_name': 'Technologies',
                'component_type': 'model',
                'model_class_name': 'Technologies',
                'description': 'Renewable energy technologies and specifications',
                'position_x': 200,
                'position_y': 300,
                'width': 120,
                'height': 60,
            },
            {
                'name': 'SupplyFactors',
                'display_name': 'Supply Factors',
                'component_type': 'model',
                'model_class_name': 'supplyfactors',
                'description': 'Supply factors and capacity calculations',
                'position_x': 350,
                'position_y': 300,
                'width': 120,
                'height': 60,
            },
            
            # Processing Modules (from your original coordinates)
            {
                'name': 'Powermap',
                'display_name': 'Power Mapping',
                'component_type': 'module',
                'description': 'Geographic mapping and visualization of power generation',
                'position_x': 550,
                'position_y': 150,
                'width': 120,
                'height': 60,
            },
            {
                'name': 'Powermatch',
                'display_name': 'Power Matching',
                'component_type': 'module',
                'description': 'Supply and demand matching optimization',
                'position_x': 550,
                'position_y': 250,
                'width': 120,
                'height': 60,
            },
            {
                'name': 'Powerplot',
                'display_name': 'Power Plotting',
                'component_type': 'module',
                'description': 'Data visualization and plotting tools',
                'position_x': 550,
                'position_y': 350,
                'width': 120,
                'height': 60,
            },
            {
                'name': 'SAM',
                'display_name': 'SAM Integration',
                'component_type': 'external',
                'description': 'System Advisor Model integration for detailed analysis',
                'position_x': 650,
                'position_y': 200,
                'width': 100,
                'height': 50,
            },
            {
                'name': 'Optimisation',
                'display_name': 'Optimization',
                'component_type': 'module',
                'description': 'System optimization and planning algorithms',
                'position_x': 200,
                'position_y': 400,
                'width': 120,
                'height': 60,
            },
        ]
        
        # Define connections between components
        connections_data = [
            # Data flows from models to processing modules
            ('Weather', 'Powermap', 'data_flow', 'Weather data feeds into power mapping'),
            ('Demand', 'Powermap', 'data_flow', 'Demand data used for power mapping'),
            ('Facilities', 'Powermap', 'data_flow', 'Facility data for geographic mapping'),
            
            # Processing flow
            ('Powermap', 'Powermatch', 'process_flow', 'Mapped data flows to matching algorithm'),
            ('Powermatch', 'Analysis', 'data_flow', 'Matching results feed analysis'),
            ('Powermatch', 'Powerplot', 'data_flow', 'Results used for visualization'),
            
            # Scenario and technology inputs
            ('Scenarios', 'Optimisation', 'data_flow', 'Scenario parameters for optimization'),
            ('Technologies', 'Optimisation', 'data_flow', 'Technology specs for optimization'),
            ('SupplyFactors', 'Powermatch', 'data_flow', 'Supply factors for matching'),
            
            # External system integration
            ('Powermap', 'SAM', 'api_call', 'Detailed modeling via SAM integration'),
            ('SAM', 'Analysis', 'data_flow', 'SAM results feed back to analysis'),
            
            # Optimization feedback
            ('Optimisation', 'Analysis', 'data_flow', 'Optimization results for analysis'),
        ]
        
        created_components = 0
        created_connections = 0
        
        with transaction.atomic():
            # Create components
            for comp_data in components_data:
                if options['dry_run']:
                    self.stdout.write(f"Would create component: {comp_data['name']}")
                else:
                    component, created = SystemComponent.objects.get_or_create(
                        name=comp_data['name'],
                        defaults=comp_data
                    )
                    if created:
                        created_components += 1
                        self.stdout.write(
                            self.style.SUCCESS(f"Created component: {component.name}")
                        )
                    else:
                        self.stdout.write(f"Component already exists: {component.name}")
            
            # Create connections
            for from_name, to_name, conn_type, description in connections_data:
                if options['dry_run']:
                    self.stdout.write(f"Would create connection: {from_name} → {to_name}")
                else:
                    try:
                        from_comp = SystemComponent.objects.get(name=from_name)
                        to_comp = SystemComponent.objects.get(name=to_name)
                        
                        connection, created = ComponentConnection.objects.get_or_create(
                            from_component=from_comp,
                            to_component=to_comp,
                            connection_type=conn_type,
                            defaults={'description': description}
                        )
                        if created:
                            created_connections += 1
                            self.stdout.write(
                                self.style.SUCCESS(f"Created connection: {connection}")
                            )
                        else:
                            self.stdout.write(f"Connection already exists: {connection}")
                    except SystemComponent.DoesNotExist as e:
                        self.stdout.write(
                            self.style.ERROR(f"Could not create connection {from_name} → {to_name}: {e}")
                        )
        
        # Summary
        if options['dry_run']:
            self.stdout.write(
                self.style.WARNING(
                    f"DRY RUN: Would create {len(components_data)} components and {len(connections_data)} connections"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully created {created_components} components and {created_connections} connections"
                )
            )
            
            # Show some statistics
            total_components = SystemComponent.objects.count()
            total_connections = ComponentConnection.objects.count()
            self.stdout.write(f"Total components in database: {total_components}")
            self.stdout.write(f"Total connections in database: {total_connections}")
            
            # Validate model connections
            self.stdout.write("\nValidating model connections...")
            model_components = SystemComponent.objects.filter(component_type='model')
            for component in model_components:
                model_class = component.get_model_class()
                if model_class:
                    try:
                        count = model_class.objects.count()
                        self.stdout.write(f"✓ {component.name}: {count} records")
                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(f"✗ {component.name}: {str(e)}")
                        )
                else:
                    self.stdout.write(
                        self.style.WARNING(f"⚠ {component.name}: Model class not found")
                    )