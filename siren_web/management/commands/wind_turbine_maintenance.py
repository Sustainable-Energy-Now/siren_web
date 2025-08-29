# management/commands/wind_turbine_maintenance.py
# Example usage:
# python manage.py wind_turbine_maintenance import --wind_turbines_csv "Wind Turbines.csv"
# python manage.py wind_turbine_maintenance stats
# python manage.py wind_turbine_maintenance report --type power_curves

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Sum, Count, F
from django.db import transaction
import os
import csv
from siren_web.models import facilities, WindTurbines, FacilityWindTurbines, TurbinePowerCurves

class Command(BaseCommand):
    help = 'Wind turbine data maintenance and reporting commands'

    def add_arguments(self, parser):
        subparsers = parser.add_subparsers(dest='action', help='Available actions')
        
        # Report generation
        report_parser = subparsers.add_parser('report', help='Generate reports')
        report_parser.add_argument('--type', choices=['summary', 'facilities', 'turbines', 'power_curves'], 
                                 default='summary', help='Type of report to generate')
        report_parser.add_argument('--output', help='Output file path (CSV format)')
        
        # Data validation
        validate_parser = subparsers.add_parser('validate', help='Validate data integrity')
        validate_parser.add_argument('--fix', action='store_true', help='Attempt to fix issues found')
        
        # Bulk import
        import_parser = subparsers.add_parser('import', help='Bulk import data')
        import_parser.add_argument('--turbines', help='CSV file with turbine models to import')
        import_parser.add_argument('--power_curves', help='Directory with .pow files to import')
        import_parser.add_argument('--wind_turbines_csv', help='Import from Wind Turbines.csv file')
        
        # Statistics
        stats_parser = subparsers.add_parser('stats', help='Show statistics')

    def handle(self, *args, **options):
        action = options.get('action')
        
        if action == 'report':
            self.generate_report(options)
        elif action == 'validate':
            self.validate_data(options)
        elif action == 'import':
            self.import_data(options)
        elif action == 'stats':
            self.show_statistics()
        else:
            self.stdout.write(self.style.ERROR('Please specify an action: report, validate, import, or stats'))

    def generate_report(self, options):
        report_type = options['type']
        output_file = options.get('output')
        
        if report_type == 'summary':
            data = self.get_summary_report()
        elif report_type == 'facilities':
            data = self.get_facilities_report()
        elif report_type == 'turbines':
            data = self.get_turbines_report()
        elif report_type == 'power_curves':
            data = self.get_power_curves_report()
        
        if output_file:
            self.write_csv_report(data, output_file)
            self.stdout.write(self.style.SUCCESS(f'Report saved to {output_file}'))
        else:
            self.print_report(data, report_type)

    def get_summary_report(self):
        total_facilities = facilities.objects.count()
        wind_facilities = facilities.objects.filter(wind_turbines__isnull=False).distinct().count()
        total_turbine_models = WindTurbines.objects.count()
        total_installations = FacilityWindTurbines.objects.filter(is_active=True).count()
        total_individual_turbines = FacilityWindTurbines.objects.filter(is_active=True).aggregate(
            total=Sum('no_turbines'))['total'] or 0
        total_capacity = FacilityWindTurbines.objects.filter(is_active=True).aggregate(
            total=Sum(F('no_turbines') * F('wind_turbine__rated_power')))['total'] or 0
        
        return {
            'summary': [
                ['Metric', 'Value'],
                ['Total Facilities', total_facilities],
                ['Wind Facilities', wind_facilities],
                ['Turbine Models', total_turbine_models],
                ['Active Installations', total_installations],
                ['Total Individual Turbines', total_individual_turbines],
                ['Total Wind Capacity (kW)', f'{total_capacity:,.0f}'],
            ]
        }

    def get_facilities_report(self):
        facilities = (
            facilities.objects
            .filter(wind_turbines__isnull=False)
            .distinct()
            .prefetch_related('facilitywindturbines_set__wind_turbine')
        )
        
        data = [['Facility Name', 'Facility Code', 'Turbine Models', 'Total Turbines', 'Total Capacity (kW)']]
        
        for facility in facilities:
            installations = facility.facilitywindturbines_set.filter(is_active=True)
            turbine_models = installations.count()
            total_turbines = sum(inst.no_turbines for inst in installations)
            total_capacity = sum(inst.total_capacity or 0 for inst in installations)
            
            data.append([
                facility.facility_name or '',
                facility.facility_code or '',
                turbine_models,
                total_turbines,
                f'{total_capacity:,.0f}'
            ])
        
        return {'facilities': data}

    def get_turbines_report(self):
        turbines = (
            WindTurbines.objects
            .annotate(
                facility_count=Count('facilities', distinct=True),
                total_installations=Sum('facilitywindturbines__no_turbines'),
                total_capacity=Sum(F('facilitywindturbines__no_turbines') * F('rated_power'))
            )
            .order_by('-total_capacity')
        )
        
        data = [['Model', 'Manufacturer', 'Rated Power (kW)', 'Facilities Using', 'Total Turbines', 'Total Capacity (kW)']]
        
        for turbine in turbines:
            data.append([
                turbine.turbine_model,
                turbine.manufacturer or '',
                turbine.rated_power or '',
                turbine.facility_count,
                turbine.total_installations or 0,
                f'{turbine.total_capacity or 0:,.0f}'
            ])
        
        return {'turbines': data}

    def get_power_curves_report(self):
        power_curves = TurbinePowerCurves.objects.select_related('wind_turbine').order_by('wind_turbine__turbine_model')
        
        data = [['Turbine Model', 'Power File', 'Active', 'Data Points', 'Upload Date']]
        
        for curve in power_curves:
            data_points = 0
            if curve.power_curve_data and isinstance(curve.power_curve_data, dict):
                wind_speeds = curve.power_curve_data.get('wind_speeds', [])
                data_points = len(wind_speeds)
            
            data.append([
                curve.wind_turbine.turbine_model,
                curve.power_file_name,
                'Yes' if curve.is_active else 'No',
                data_points,
                curve.file_upload_date.strftime('%Y-%m-%d')
            ])
        
        return {'power_curves': data}

    def print_report(self, data, report_type):
        self.stdout.write(self.style.SUCCESS(f'\n=== {report_type.upper()} REPORT ===\n'))
        
        for section_name, section_data in data.items():
            if section_data:
                # Print headers
                headers = section_data[0]
                self.stdout.write('  '.join(f'{h:<20}' for h in headers))
                self.stdout.write('-' * (len(headers) * 22))
                
                # Print data rows
                for row in section_data[1:]:
                    self.stdout.write('  '.join(f'{str(cell):<20}' for cell in row))
                
                self.stdout.write('')

    def write_csv_report(self, data, output_file):
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            
            for section_name, section_data in data.items():
                if section_data:
                    writer.writerow([f'=== {section_name.upper()} ==='])
                    writer.writerows(section_data)
                    writer.writerow([])  # Empty row between sections

    def validate_data(self, options):
        fix_issues = options.get('fix', False)
        issues_found = []
        
        self.stdout.write('Validating wind turbine data...\n')
        
        # Check for facilities with turbine data but no FacilityWindTurbines records
        facilities_with_old_data = facilities.objects.filter(
            turbine__isnull=False
        ).exclude(turbine='').exclude(
            id__in=FacilityWindTurbines.objects.values_list('facility_id', flat=True)
        )
        
        if facilities_with_old_data.exists():
            count = facilities_with_old_data.count()
            issues_found.append(f"Found {count} facilities with old turbine data not migrated")
            if fix_issues:
                self.stdout.write(f'Fixing {count} facilities with unmigrated data...')
                # Could add migration logic here
        
        # Check for power curves without data
        empty_power_curves = TurbinePowerCurves.objects.filter(
            power_curve_data__isnull=True
        ) | TurbinePowerCurves.objects.filter(
            power_curve_data={}
        )
        
        if empty_power_curves.exists():
            count = empty_power_curves.count()
            issues_found.append(f"Found {count} power curves without data")
            if fix_issues:
                self.stdout.write(f'Marking {count} empty power curves as inactive...')
                empty_power_curves.update(is_active=False)
        
        # Check for turbines without rated power
        turbines_no_power = WindTurbines.objects.filter(rated_power__isnull=True)
        if turbines_no_power.exists():
            count = turbines_no_power.count()
            issues_found.append(f"Found {count} turbine models without rated power")
        
        # Check for installations with zero turbines
        zero_turbine_installs = FacilityWindTurbines.objects.filter(no_turbines__lte=0)
        if zero_turbine_installs.exists():
            count = zero_turbine_installs.count()
            issues_found.append(f"Found {count} installations with zero or negative turbines")
            if fix_issues:
                self.stdout.write(f'Marking {count} zero-turbine installations as inactive...')
                zero_turbine_installs.update(is_active=False)
        
        if issues_found:
            self.stdout.write(self.style.WARNING('Issues found:'))
            for issue in issues_found:
                self.stdout.write(f'  - {issue}')
        else:
            self.stdout.write(self.style.SUCCESS('No data issues found!'))

    def import_data(self, options):
        turbines_file = options.get('turbines')
        power_curves_dir = options.get('power_curves')
        wind_turbines_csv = options.get('wind_turbines_csv')
        
        if turbines_file:
            self.import_turbine_models(turbines_file)
        
        if power_curves_dir:
            self.import_power_curves(power_curves_dir)
        
        if wind_turbines_csv:
            self.import_wind_turbines_csv(wind_turbines_csv)

    def import_wind_turbines_csv(self, csv_file):
        """Import turbine models and power curves from the Wind Turbines.csv file"""
        if not os.path.exists(csv_file):
            raise CommandError(f'File not found: {csv_file}')
        
        self.stdout.write(f'Importing wind turbine data from {csv_file}...')
        
        with open(csv_file, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            
            created_turbines = 0
            updated_turbines = 0
            created_power_curves = 0
            skipped_rows = 0
            
            with transaction.atomic():
                for row_num, row in enumerate(reader, 1):
                    # Skip header rows (Units and column descriptions)
                    if row_num <= 2:
                        continue
                    
                    name = row.get('Name', '').strip()
                    if not name:
                        skipped_rows += 1
                        continue
                    
                    try:
                        # Extract turbine specifications
                        kw_rating = self._parse_float(row.get('KW Rating'))
                        rotor_diameter = self._parse_float(row.get('Rotor Diameter'))
                        iec_class = row.get('IEC Wind Speed Class', '').strip()
                        wind_speed_array = row.get('Wind Speed Array', '').strip()
                        power_curve_array = row.get('Power Curve Array', '').strip()
                        
                        # Extract manufacturer from name if possible
                        manufacturer = self._extract_manufacturer(name)
                        
                        # Create or update wind turbine model
                        turbine, created = WindTurbines.objects.get_or_create(
                            turbine_model=name,
                            defaults={
                                'manufacturer': manufacturer,
                                'rated_power': kw_rating,
                                'rotor_diameter': rotor_diameter,
                            }
                        )
                        
                        if created:
                            created_turbines += 1
                            self.stdout.write(f'  Created turbine: {name}')
                        else:
                            # Update existing turbine if data is better
                            updated = False
                            if not turbine.manufacturer and manufacturer:
                                turbine.manufacturer = manufacturer
                                updated = True
                            if not turbine.rated_power and kw_rating:
                                turbine.rated_power = kw_rating
                                updated = True
                            if not turbine.rotor_diameter and rotor_diameter:
                                turbine.rotor_diameter = rotor_diameter
                                updated = True
                            
                            if updated:
                                turbine.save()
                                updated_turbines += 1
                        
                        # Create power curve if data exists
                        if wind_speed_array and power_curve_array:
                            wind_speeds = self._parse_array(wind_speed_array)
                            power_outputs = self._parse_array(power_curve_array)
                            
                            if wind_speeds and power_outputs and len(wind_speeds) == len(power_outputs):
                                power_curve_data = {
                                    'wind_speeds': wind_speeds,
                                    'power_outputs': power_outputs,
                                    'data_points': len(wind_speeds),
                                    'iec_class': iec_class if iec_class != 'unknown' else None,
                                    'source': 'Wind_Turbines_CSV'
                                }
                                
                                # Create power curve (use unique filename based on turbine name)
                                power_file_name = f"{name.replace(' ', '_')}_power_curve.csv"
                                
                                power_curve, pc_created = TurbinePowerCurves.objects.get_or_create(
                                    idwindturbines=turbine,
                                    power_file_name=power_file_name,
                                    defaults={
                                        'power_curve_data': power_curve_data,
                                        'is_active': True,
                                        'notes': f'Imported from Wind Turbines CSV. IEC Class: {iec_class}'
                                    }
                                )
                                
                                if pc_created:
                                    created_power_curves += 1
                    
                    except Exception as e:
                        self.stdout.write(
                            self.style.WARNING(f'  Error processing row {row_num} ({name}): {str(e)}')
                        )
                        skipped_rows += 1
                        continue
        
        # Print summary
        self.stdout.write(self.style.SUCCESS(
            f'\nImport completed:\n'
            f'  - Turbine models created: {created_turbines}\n'
            f'  - Turbine models updated: {updated_turbines}\n'
            f'  - Power curves created: {created_power_curves}\n'
            f'  - Rows skipped: {skipped_rows}'
        ))

    def _parse_float(self, value):
        """Safely parse a float value"""
        if value is None or value == '' or value == 'unknown':
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    def _parse_array(self, array_str):
        """Parse pipe-separated array string into list of floats"""
        if not array_str or array_str == 'unknown':
            return []
        try:
            return [float(x.strip()) for x in array_str.split('|') if x.strip()]
        except (ValueError, TypeError):
            return []

    def _extract_manufacturer(self, turbine_name):
        """Extract manufacturer name from turbine model string"""
        # Common manufacturer patterns in the data
        manufacturers = [
            'Vestas', 'Enercon', 'Siemens', 'Gamesa', 'Suzlon', 'Nordex',
            'Acciona', 'Alstom', 'DeWind', 'Fuhrlaender', 'Goldwind',
            'Mitsubishi', 'REpower', 'Senvion', 'Unison', 'WinWinD',
            'Ampair', 'Bergey', 'Southwest Windpower', 'Proven', 'Kestrel',
            'Marlec', 'Future Energy', 'Earth-Tech', 'Energy Ball'
        ]
        
        name_upper = turbine_name.upper()
        for mfg in manufacturers:
            if mfg.upper() in name_upper:
                return mfg
        
        # Try to extract first word as manufacturer for some patterns
        first_word = turbine_name.split()[0] if turbine_name.split() else None
        if first_word and len(first_word) > 2 and not first_word.isdigit():
            return first_word
        
        return None

    def import_turbine_models(self, csv_file):
        if not os.path.exists(csv_file):
            raise CommandError(f'File not found: {csv_file}')
        
        with open(csv_file, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            created_count = 0
            updated_count = 0
            
            for row in reader:
                turbine_model = row.get('turbine_model', '').strip()
                if not turbine_model:
                    continue
                
                turbine, created = WindTurbines.objects.get_or_create(
                    turbine_model=turbine_model,
                    defaults={
                        'manufacturer': row.get('manufacturer', '').strip() or None,
                        'hub_height': float(row['hub_height']) if row.get('hub_height') else None,
                        'rated_power': float(row['rated_power']) if row.get('rated_power') else None,
                        'rotor_diameter': float(row['rotor_diameter']) if row.get('rotor_diameter') else None,
                        'cut_in_speed': float(row['cut_in_speed']) if row.get('cut_in_speed') else None,
                        'cut_out_speed': float(row['cut_out_speed']) if row.get('cut_out_speed') else None,
                    }
                )
                
                if created:
                    created_count += 1
                else:
                    # Update existing record
                    for field in ['manufacturer', 'hub_height', 'rated_power', 'rotor_diameter', 'cut_in_speed', 'cut_out_speed']:
                        if row.get(field):
                            value = row[field].strip() if field == 'manufacturer' else float(row[field])
                            setattr(turbine, field, value)
                    turbine.save()
                    updated_count += 1
        
        self.stdout.write(self.style.SUCCESS(
            f'Import complete: {created_count} created, {updated_count} updated'
        ))

    def show_statistics(self):
        self.stdout.write(self.style.SUCCESS('=== WIND TURBINE STATISTICS ===\n'))
        
        # Basic counts
        stats = {
            'Total Facilities': facilities.objects.count(),
            'Wind Facilities': facilities.objects.filter(wind_turbines__isnull=False).distinct().count(),
            'Turbine Models': WindTurbines.objects.count(),
            'Active Installations': FacilityWindTurbines.objects.filter(is_active=True).count(),
            'Power Curves': TurbinePowerCurves.objects.count(),
        }
        
        for key, value in stats.items():
            self.stdout.write(f'{key}: {value:,}')
        
        # Top manufacturers
        self.stdout.write('\nTop Manufacturers by Capacity:')
        top_manufacturers = (
            FacilityWindTurbines.objects
            .filter(is_active=True, wind_turbine__manufacturer__isnull=False)
            .values('wind_turbine__manufacturer')
            .annotate(
                total_capacity=Sum(F('no_turbines') * F('wind_turbine__rated_power'))
            )
            .order_by('-total_capacity')[:5]
        )
        
        for mfg in top_manufacturers:
            name = mfg['wind_turbine__manufacturer']
            capacity = mfg['total_capacity'] or 0
            self.stdout.write(f'  {name}: {capacity:,.0f} kW')
