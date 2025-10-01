# Create this file as: siren_web/management/commands/create_sample_terminals.py
from django.core.management.base import BaseCommand
from siren_web.models import Terminals, GridLines

class Command(BaseCommand):
    help = 'Create sample terminals and link existing grid lines to them'

    def add_arguments(self, parser):
        parser.add_argument(
            '--create-samples',
            action='store_true',
            help='Create sample terminal data',
        )
        parser.add_argument(
            '--link-existing',
            action='store_true', 
            help='Attempt to link existing grid lines to nearest terminals',
        )

    def handle(self, *args, **options):
        if options['create_samples']:
            self.create_sample_terminals()
            
        if options['link_existing']:
            self.link_existing_grid_lines()

    def create_sample_terminals(self):
        """Create some sample terminals for demonstration"""
        sample_terminals = [
            {
                'terminal_name': 'Perth Terminal Station',
                'terminal_code': 'PTS',
                'terminal_type': 'transmission_substation',
                'latitude': -31.9505, 
                'longitude': 115.8605,
                'primary_voltage_kv': 330.0,
                'secondary_voltage_kv': 132.0,
                'transformer_capacity_mva': 500.0,
                'bay_count': 8,
                'owner': 'Western Power',
                'description': 'Main transmission terminal for Perth metropolitan area'
            },
            {
                'terminal_name': 'Kwinana Terminal',
                'terminal_code': 'KWT',
                'terminal_type': 'substation',
                'latitude': -32.2378,
                'longitude': 115.7839, 
                'primary_voltage_kv': 220.0,
                'secondary_voltage_kv': 66.0,
                'transformer_capacity_mva': 250.0,
                'bay_count': 6,
                'owner': 'Western Power',
                'description': 'Industrial area terminal serving Kwinana'
            },
            {
                'terminal_name': 'Geraldton Substation',
                'terminal_code': 'GTS',
                'terminal_type': 'distribution_substation',
                'latitude': -28.7774,
                'longitude': 114.6130,
                'primary_voltage_kv': 132.0,
                'secondary_voltage_kv': 33.0,
                'transformer_capacity_mva': 100.0,
                'bay_count': 4,
                'owner': 'Western Power',
                'description': 'Regional terminal for Geraldton area'
            },
            {
                'terminal_name': 'Albany Terminal',
                'terminal_code': 'ALT',
                'terminal_type': 'switching_station',
                'latitude': -35.0269,
                'longitude': 117.8840,
                'primary_voltage_kv': 132.0,
                'transformer_capacity_mva': 75.0,
                'bay_count': 3,
                'owner': 'Western Power',
                'description': 'Terminal serving Albany and Great Southern region'
            }
        ]
        
        created_count = 0
        for terminal_data in sample_terminals:
            # Check if terminal already exists
            if not Terminals.objects.filter(
                terminal_code=terminal_data['terminal_code']
            ).exists():
                
                # Determine voltage class
                voltage_kv = terminal_data['primary_voltage_kv']
                if voltage_kv >= 800:
                    voltage_class = 'ultra_high'
                elif voltage_kv >= 138:
                    voltage_class = 'extra_high'
                elif voltage_kv >= 35:
                    voltage_class = 'high'
                elif voltage_kv >= 1:
                    voltage_class = 'medium'
                else:
                    voltage_class = 'low'
                
                terminal_data['voltage_class'] = voltage_class
                
                terminal = Terminals.objects.create(**terminal_data)
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'Created terminal: {terminal.terminal_name}')
                )
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully created {created_count} sample terminals')
        )

    def link_existing_grid_lines(self):
        """Attempt to link existing grid lines to nearest terminals"""
        linked_count = 0
        terminals = list(Terminals.objects.filter(active=True))
        
        if not terminals:
            self.stdout.write(
                self.style.WARNING('No terminals found. Create terminals first.')
            )
            return
        
        for grid_line in GridLines.objects.filter(active=True):
            # Skip if already has terminal connections
            if grid_line.from_terminal or grid_line.to_terminal:
                continue
            
            # Find nearest terminals to start and end points
            from_terminal = self.find_nearest_terminal(
                grid_line.from_latitude, grid_line.from_longitude, terminals
            )
            to_terminal = self.find_nearest_terminal(
                grid_line.to_latitude, grid_line.to_longitude, terminals
            )
            
            # Only link if terminals are reasonably close (within 50km)
            from_distance = self.calculate_distance(
                grid_line.from_latitude, grid_line.from_longitude,
                from_terminal.latitude, from_terminal.longitude
            ) if from_terminal else float('inf')
            
            to_distance = self.calculate_distance(
                grid_line.to_latitude, grid_line.to_longitude, 
                to_terminal.latitude, to_terminal.longitude
            ) if to_terminal else float('inf')
            
            updated = False
            if from_distance <= 50:  # 50km threshold
                grid_line.from_terminal = from_terminal
                updated = True
                
            if to_distance <= 50:  # 50km threshold
                grid_line.to_terminal = to_terminal
                updated = True
                
            if updated:
                grid_line.save()
                linked_count += 1
                self.stdout.write(
                    f'Linked {grid_line.line_name} to terminals'
                )
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully linked {linked_count} grid lines to terminals')
        )

    def find_nearest_terminal(self, lat, lon, terminals):
        """Find the nearest terminal to given coordinates"""
        min_distance = float('inf')
        nearest_terminal = None
        
        for terminal in terminals:
            distance = self.calculate_distance(
                lat, lon, terminal.latitude, terminal.longitude
            )
            if distance < min_distance:
                min_distance = distance
                nearest_terminal = terminal
        
        return nearest_terminal

    def calculate_distance(self, lat1, lon1, lat2, lon2):
        """Calculate distance between two points using Haversine formula"""
        import math
        R = 6371  # Earth's radius in kilometers
        
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        
        return R * c


# Create these CSS classes for terminal icons in your static/icons/ directory
# You can use simple colored squares or create custom SVG icons

# Example CSS for terminal markers (add to your CSS):
"""
.terminal-icon {
    width: 30px;
    height: 30px;
    border-radius: 4px;
    border: 2px solid #333;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 10px;
    font-weight: bold;
    color: white;
    text-shadow: 1px 1px 1px rgba(0,0,0,0.5);
}

.terminal-substation {
    background-color: #4CAF50;
}

.terminal-switching-station {
    background-color: #2196F3;
}

.terminal-transmission-substation {
    background-color: #FF5722;
}

.terminal-distribution-substation {
    background-color: #9C27B0;
}

.terminal-converter-station {
    background-color: #FF9800;
}

.terminal-station {
    background-color: #607D8B;
}
"""

# Example simple SVG icons - create these as separate files in static/icons/

# terminal_substation.svg
terminal_substation_svg = """
<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32">
    <rect x="4" y="8" width="24" height="16" fill="#4CAF50" stroke="#333" stroke-width="2" rx="2"/>
    <circle cx="12" cy="16" r="2" fill="white"/>
    <circle cx="20" cy="16" r="2" fill="white"/>
    <line x1="16" y1="8" x2="16" y2="24" stroke="#333" stroke-width="1"/>
    <text x="16" y="18" text-anchor="middle" fill="white" font-size="8" font-weight="bold">T</text>
</svg>
"""

# terminal_high_voltage.svg  
terminal_high_voltage_svg = """
<svg xmlns="http://www.w3.org/2000/svg" width="36" height="36" viewBox="0 0 36 36">
    <rect x="2" y="6" width="32" height="24" fill="#FF5722" stroke="#333" stroke-width="2" rx="3"/>
    <polygon points="18,10 22,18 14,18" fill="yellow"/>
    <circle cx="10" cy="20" r="2" fill="white"/>
    <circle cx="18" cy="20" r="2" fill="white"/>
    <circle cx="26" cy="20" r="2" fill="white"/>
    <text x="18" y="28" text-anchor="middle" fill="white" font-size="6" font-weight="bold">HV</text>
</svg>
"""