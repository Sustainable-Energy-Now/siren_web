import xml.etree.ElementTree as ET
from django.core.management.base import BaseCommand
from django.conf import settings
from siren_web.models import GridLines
import os
import re
import math

class Command(BaseCommand):
    help = 'Import KML transmission lines into GridLines database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--kml-file',
            type=str,
            help='Path to KML file (relative to static directory)',
            default='kml/SWIS_Grid.kml'
        )
        parser.add_argument(
            '--update-existing',
            action='store_true',
            help='Update existing grid lines if found',
        )
        parser.add_argument(
            '--default-voltage',
            type=float,
            default=132.0,
            help='Default voltage level for lines without voltage info',
        )

    def handle(self, *args, **options):
        kml_file_path = os.path.join(settings.STATIC_ROOT or 'static', options['kml_file'])
        
        if not os.path.exists(kml_file_path):
            kml_file_path = os.path.join('static', options['kml_file'])
        
        if not os.path.exists(kml_file_path):
            self.stdout.write(
                self.style.ERROR(f'KML file not found: {kml_file_path}')
            )
            return

        self.stdout.write(f'Importing KML from: {kml_file_path}')
        
        try:
            tree = ET.parse(kml_file_path)
            root = tree.getroot()
            
            # Handle KML namespaces
            namespaces = {
                'kml': 'http://www.opengis.net/kml/2.2',
                'gx': 'http://www.google.com/kml/ext/2.2'
            }
            
            imported_count = 0
            updated_count = 0
            skipped_count = 0
            
            # Find all Placemark elements (transmission lines)
            placemarks = root.findall('.//kml:Placemark', namespaces)
            
            for placemark in placemarks:
                result = self.process_placemark(placemark, namespaces, options)
                if result == 'imported':
                    imported_count += 1
                elif result == 'updated':
                    updated_count += 1
                else:
                    skipped_count += 1
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Import complete: {imported_count} imported, '
                    f'{updated_count} updated, {skipped_count} skipped'
                )
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error importing KML: {str(e)}')
            )

    def process_placemark(self, placemark, namespaces, options):
        """Process a single KML Placemark into a GridLine"""
        
        # Extract name
        name_elem = placemark.find('kml:name', namespaces)
        line_name = name_elem.text if name_elem is not None else 'Unknown Line'
        
        # Extract description (may contain voltage and other info)
        desc_elem = placemark.find('kml:description', namespaces)
        description = desc_elem.text if desc_elem is not None else ''
        
        # Extract style URL to determine voltage level
        style_elem = placemark.find('kml:styleUrl', namespaces)
        style_url = style_elem.text if style_elem is not None else ''
        
        # Extract LineString coordinates
        linestring = placemark.find('.//kml:LineString/kml:coordinates', namespaces)
        if linestring is None:
            self.stdout.write(f'Skipping {line_name}: No LineString found')
            return 'skipped'
        
        coordinates_text = linestring.text.strip()
        coords = self.parse_coordinates(coordinates_text)
        
        if len(coords) < 2:
            self.stdout.write(f'Skipping {line_name}: Invalid coordinates')
            return 'skipped'
        
        # Use first and last coordinates as endpoints
        from_coord = coords[0]
        to_coord = coords[-1]
        
        # Parse voltage from style URL, name or description
        voltage_level = self.extract_voltage_from_style_and_name(style_url, line_name, description, options['default_voltage'])
        
        # Generate line code from name
        line_code = self.generate_line_code(line_name)
        
        # Calculate length
        length_km = self.calculate_total_length(coords)
        
        # Determine line type based on voltage
        line_type = self.determine_line_type(voltage_level)
        
        # Store full coordinate data as KML geometry
        kml_geometry_data = {
            'type': 'LineString',
            'coordinates': coords,
            'name': line_name,
            'description': description,
            'style_url': style_url
        }
        
        # Check if grid line already exists
        existing_line = None
        try:
            existing_line = GridLines.objects.get(line_name=line_name)
        except GridLines.DoesNotExist:
            try:
                existing_line = GridLines.objects.get(line_code=line_code)
            except GridLines.DoesNotExist:
                pass
        
        if existing_line:
            if options['update_existing']:
                # Update existing line
                existing_line.line_code = line_code
                existing_line.line_type = line_type
                existing_line.voltage_level = voltage_level
                existing_line.length_km = length_km
                existing_line.from_latitude = from_coord[1]
                existing_line.from_longitude = from_coord[0]
                existing_line.to_latitude = to_coord[1]
                existing_line.to_longitude = to_coord[0]
                existing_line.set_kml_geometry_data(kml_geometry_data)
                existing_line.save()
                
                self.stdout.write(f'Updated: {line_name} ({voltage_level}kV)')
                return 'updated'
            else:
                self.stdout.write(f'Skipped existing: {line_name}')
                return 'skipped'
        else:
            # Create new grid line
            grid_line = GridLines.objects.create(
                line_name=line_name,
                line_code=line_code,
                line_type=line_type,
                voltage_level=voltage_level,
                length_km=length_km,
                resistance_per_km=self.estimate_resistance(voltage_level),
                reactance_per_km=self.estimate_reactance(voltage_level),
                thermal_capacity_mw=self.estimate_capacity(voltage_level),
                from_latitude=from_coord[1],
                from_longitude=from_coord[0],
                to_latitude=to_coord[1],
                to_longitude=to_coord[0],
                owner='Western Power',  # SWIS operator
                active=True
            )
            
            # Store KML geometry data
            grid_line.set_kml_geometry_data(kml_geometry_data)
            grid_line.save()
            
            self.stdout.write(f'Imported: {line_name} ({voltage_level}kV, {length_km}km)')
            return 'imported'

    def extract_voltage_from_style_and_name(self, style_url, name, description, default_voltage):
        """Extract voltage level from style URL, name, or description"""
        
        # First try to extract from style URL
        if style_url:
            style_voltage_map = {
                's_330kv': 330.0,
                's_220kv': 220.0, 
                's_132kv': 132.0,
                's_66kv': 66.0
            }
            
            for style, voltage in style_voltage_map.items():
                if style in style_url:
                    return voltage
        
        # Then try to extract from name
        if name:
            if '330KV' in name.upper() or '330' in name:
                return 330.0
            elif '220KV' in name.upper() or '220' in name:
                return 220.0
            elif '132KV' in name.upper() or '132' in name:
                return 132.0
            elif '66KV' in name.upper() or '66' in name:
                return 66.0
        
        # Finally try the original voltage extraction method
        return self.extract_voltage(name, description, default_voltage)

    def parse_coordinates(self, coordinates_text):
        """Parse KML coordinates string into list of [lon, lat, alt] arrays"""
        coords = []
        coord_pairs = coordinates_text.strip().split()
        
        for coord_str in coord_pairs:
            parts = coord_str.split(',')
            if len(parts) >= 2:
                try:
                    lon = float(parts[0])
                    lat = float(parts[1])
                    alt = float(parts[2]) if len(parts) > 2 else 0
                    coords.append([lon, lat, alt])
                except ValueError:
                    continue
        
        return coords

    def extract_voltage(self, name, description, default_voltage):
        """Extract voltage level from name or description"""
        text = f"{name} {description}".lower()
        
        # Common voltage patterns
        voltage_patterns = [
            r'(\d+)\s*kv',
            r'(\d+)\s*kilovolt',
            r'(\d+)kv',
            r'(\d{2,3})\s*k\s*v'
        ]
        
        for pattern in voltage_patterns:
            match = re.search(pattern, text)
            if match:
                voltage = float(match.group(1))
                # Validate reasonable voltage levels
                if 1 <= voltage <= 800:
                    return voltage
        
        # Try to infer from common naming conventions
        if any(term in text for term in ['transmission', 'high voltage', 'hv']):
            return 220.0
        elif any(term in text for term in ['distribution', 'medium voltage', 'mv']):
            return 33.0
        elif any(term in text for term in ['low voltage', 'lv']):
            return 11.0
        
        return default_voltage

    def generate_line_code(self, line_name):
        """Generate a unique line code from the line name"""
        # Remove common words and create acronym
        common_words = ['transmission', 'line', 'to', 'and', 'the', 'of', 'at']
        words = re.findall(r'\b\w+\b', line_name.lower())
        
        significant_words = [w for w in words if w not in common_words and len(w) > 1]
        
        if not significant_words:
            significant_words = words[:3]  # Use first 3 words if no significant words
        
        # Create code from first letters or first few letters of words
        code_parts = []
        for word in significant_words[:4]:  # Max 4 words
            if len(word) <= 3:
                code_parts.append(word.upper())
            else:
                code_parts.append(word[:3].upper())
        
        base_code = '_'.join(code_parts)
        
        # Ensure uniqueness
        counter = 1
        final_code = base_code
        while GridLines.objects.filter(line_code=final_code).exists():
            final_code = f"{base_code}_{counter}"
            counter += 1
        
        return final_code[:30]  # Respect max length

    def calculate_total_length(self, coords):
        """Calculate total length of line following all coordinates"""
        total_length = 0
        
        for i in range(1, len(coords)):
            prev_coord = coords[i-1]
            curr_coord = coords[i]
            
            # Haversine formula for distance between two points
            lat1, lon1 = math.radians(prev_coord[1]), math.radians(prev_coord[0])
            lat2, lon2 = math.radians(curr_coord[1]), math.radians(curr_coord[0])
            
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            
            a = (math.sin(dlat/2)**2 + 
                 math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2)
            c = 2 * math.asin(math.sqrt(a))
            
            distance = 6371 * c  # Earth's radius in km
            total_length += distance
        
        return round(total_length, 2)

    def determine_line_type(self, voltage_level):
        """Determine line type based on voltage level"""
        if voltage_level >= 220:
            return 'transmission'
        elif voltage_level >= 66:
            return 'subtransmission'
        else:
            return 'distribution'

    def estimate_resistance(self, voltage_level):
        """Estimate resistance per km based on voltage level"""
        resistance_map = {
            800: 0.02,   # EHV
            500: 0.03,   # EHV  
            330: 0.05,   # HV
            220: 0.08,   # HV
            132: 0.12,   # HV
            66: 0.25,    # MV
            33: 0.4,     # MV
            11: 0.8      # LV
        }
        
        # Find closest voltage level
        closest_voltage = min(resistance_map.keys(), key=lambda x: abs(x - voltage_level))
        return resistance_map[closest_voltage]

    def estimate_reactance(self, voltage_level):
        """Estimate reactance per km based on voltage level"""
        # Typical X/R ratio is around 3-5 for transmission lines
        resistance = self.estimate_resistance(voltage_level)
        return resistance * 4.0

    def estimate_capacity(self, voltage_level):
        """Estimate thermal capacity based on voltage level"""
        capacity_map = {
            800: 2000,   # EHV
            500: 1500,   # EHV
            330: 800,    # HV
            220: 400,    # HV
            132: 200,    # HV
            66: 100,     # MV
            33: 50,      # MV
            11: 20       # LV
        }
        
        # Find closest voltage level
        closest_voltage = min(capacity_map.keys(), key=lambda x: abs(x - voltage_level))
        return capacity_map[closest_voltage]