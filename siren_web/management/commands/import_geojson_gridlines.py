import json
from django.core.management.base import BaseCommand
from django.conf import settings
from siren_web.models import GridLines
import os
import re
import math

class Command(BaseCommand):
    help = 'Import GeoJSON transmission lines into GridLines database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--geojson-file',
            type=str,
            help='Path to GeoJSON file (relative to parent directory)',
            default='geojson/transmission_lines.geojson'
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
        geojson_file_path = os.path.join(settings.STATIC_ROOT or 'static', options['geojson_file'])
        
        if not os.path.exists(geojson_file_path):
            geojson_file_path = os.path.join('static', options['geojson_file'])
        
        if not os.path.exists(geojson_file_path):
            self.stdout.write(
                self.style.ERROR(f'GeoJSON file not found: {geojson_file_path}')
            )
            return

        self.stdout.write(f'Importing GeoJSON from: {geojson_file_path}')
        
        try:
            with open(geojson_file_path, 'r', encoding='utf-8') as f:
                geojson_data = json.load(f)
            
            if geojson_data.get('type') != 'FeatureCollection':
                self.stdout.write(
                    self.style.ERROR('Invalid GeoJSON: Expected FeatureCollection')
                )
                return
            
            imported_count = 0
            updated_count = 0
            skipped_count = 0
            
            # Process each feature (transmission line)
            features = geojson_data.get('features', [])
            
            for feature in features:
                result = self.process_feature(feature, options)
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
                self.style.ERROR(f'Error importing GeoJSON: {str(e)}')
            )

    def process_feature(self, feature, options):
        """Process a single GeoJSON Feature into a GridLine"""
        
        if feature.get('type') != 'Feature':
            return 'skipped'
        
        properties = feature.get('properties', {})
        geometry = feature.get('geometry', {})
        
        # Extract line name from properties
        line_name = properties.get('line_name', 'Unknown Line')
        
        # Extract voltage level from properties
        voltage_level = self.extract_voltage_from_properties(properties, options['default_voltage'])
        
        # Extract other properties
        installation_year = properties.get('instln_yr', '')
        reported_length = properties.get('len_km', '')
        
        # Process geometry to get coordinates
        coords = self.extract_coordinates_from_geometry(geometry)
        
        if len(coords) < 2:
            self.stdout.write(f'Skipping {line_name}: Invalid or insufficient coordinates')
            return 'skipped'
        
        # Use first and last coordinates as endpoints
        from_coord = coords[0]
        to_coord = coords[-1]
        
        # Generate line code from name
        line_code = self.generate_line_code(line_name)
        
        # Calculate length from coordinates
        calculated_length = self.calculate_total_length(coords)
        
        # Use reported length if available, otherwise use calculated
        if reported_length and str(reported_length).replace('.', '').isdigit():
            length_km = float(reported_length)
        else:
            length_km = calculated_length
        
        # Determine line type based on voltage
        line_type = self.determine_line_type(voltage_level)
        
        # Store full geometry data as GeoJSON
        geojson_geometry_data = {
            'type': 'Feature',
            'properties': properties,
            'geometry': geometry
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
                existing_line.set_kml_geometry_data(geojson_geometry_data)  # Assuming this method can handle GeoJSON too
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
            
            # Store GeoJSON geometry data
            grid_line.set_kml_geometry_data(geojson_geometry_data)  # Assuming this method can handle GeoJSON too
            grid_line.save()
            
            self.stdout.write(f'Imported: {line_name} ({voltage_level}kV, {length_km}km)')
            return 'imported'

    def extract_voltage_from_properties(self, properties, default_voltage):
        """Extract voltage level from GeoJSON properties"""
        
        # Check for 'kv' field first (as in the sample)
        kv_value = properties.get('kv', '')
        if kv_value:
            try:
                voltage = float(kv_value)
                if 1 <= voltage <= 800:
                    return voltage
            except ValueError:
                pass
        
        # Check line_name for voltage indicators
        line_name = properties.get('line_name', '')
        if line_name:
            voltage = self.extract_voltage_from_text(line_name, default_voltage)
            if voltage != default_voltage:
                return voltage
        
        # Check other common property names
        for prop_name in ['voltage', 'voltage_kv', 'kv_rating', 'nominal_voltage']:
            if prop_name in properties:
                try:
                    voltage = float(properties[prop_name])
                    if 1 <= voltage <= 800:
                        return voltage
                except (ValueError, TypeError):
                    pass
        
        return default_voltage

    def extract_coordinates_from_geometry(self, geometry):
        """Extract coordinates from GeoJSON geometry"""
        coords = []
        
        geometry_type = geometry.get('type', '')
        coordinates = geometry.get('coordinates', [])
        
        if geometry_type == 'LineString':
            # Simple LineString
            coords = coordinates
        elif geometry_type == 'MultiLineString':
            # MultiLineString - concatenate all line strings
            for line_coords in coordinates:
                coords.extend(line_coords)
        else:
            self.stdout.write(f'Warning: Unsupported geometry type: {geometry_type}')
            return []
        
        # Convert to [lon, lat, alt] format if needed
        processed_coords = []
        for coord in coords:
            if len(coord) >= 2:
                lon = coord[0]
                lat = coord[1]
                alt = coord[2] if len(coord) > 2 else 0
                processed_coords.append([lon, lat, alt])
        
        return processed_coords

    def extract_voltage_from_text(self, text, default_voltage):
        """Extract voltage level from text using regex patterns"""
        text_lower = text.lower()
        
        # Common voltage patterns
        voltage_patterns = [
            r'(\d+)\s*kv',
            r'(\d+)\s*kilovolt',
            r'(\d+)kv',
            r'(\d{2,3})\s*k\s*v'
        ]
        
        for pattern in voltage_patterns:
            match = re.search(pattern, text_lower)
            if match:
                voltage = float(match.group(1))
                # Validate reasonable voltage levels
                if 1 <= voltage <= 800:
                    return voltage
        
        # Try to infer from common naming conventions
        if any(term in text_lower for term in ['transmission', 'high voltage', 'hv']):
            return 220.0
        elif any(term in text_lower for term in ['distribution', 'medium voltage', 'mv']):
            return 33.0
        elif any(term in text_lower for term in ['low voltage', 'lv']):
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