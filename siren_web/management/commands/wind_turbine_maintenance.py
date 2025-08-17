# management/commands/wind_turbine_maintenance.py

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Sum, Count, F
import os
import csv
from siren_web.models import Facilities, WindTurbines, FacilityWindTurbines, TurbinePowerCurves


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
        total_facilities = Facilities.objects.count()
        wind_facilities = Facilities.objects.filter(wind_turbines__isnull=False).distinct().count()
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
            Facilities.objects
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
        power_curves = TurbinePowerCurve.objects.select_related('wind_turbine').order_by('wind_turbine__turbine_model')
        
        data = [['Turbine Model', 'Power File', 'Active', 'Data Points', 'Upload Date']]
        
        for curve in power_curves:
            data_points = 0
            if curve.power_curve_data and isinstance(curve.power_curve_data, dict):
                data_points = curve.power_curve_data.get('data_points', 0)
            
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
        facilities_with_old_data = Facilities.objects.filter(
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
        empty_power_curves = TurbinePowerCurve.objects.filter(
            power_curve_data__isnull=True
        ) | TurbinePowerCurve.objects.filter(
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
        
        if turbines_file:
            self.import_turbine_models(turbines_file)
        
        if power_curves_dir:
            self.import_power_curves(power_curves_dir)

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
            'Total Facilities': Facilities.objects.count(),
            'Wind Facilities': Facilities.objects.filter(wind_turbines__isnull=False).distinct().count(),
            'Turbine Models': WindTurbines.objects.count(),
            'Active Installations': FacilityWindTurbines.objects.filter(is_active=True).count(),
            'Power Curves': TurbinePowerCurve.objects.count(),
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


# Example CSV format for turbine import (save as turbines.csv):
"""
turbine_model,manufacturer,hub_height,rated_power,rotor_diameter,cut_in_speed,cut_out_speed
V90-2.0,Vestas,80,2000,90,4,25
GE 1.5-77,General Electric,80,1500,77,3.5,25
E-82,Enercon,78,2000,82,2.5,28
"""