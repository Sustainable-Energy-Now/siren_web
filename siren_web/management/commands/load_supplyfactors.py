import csv
import os
from django.core.management.base import BaseCommand, CommandError
from siren_web.models import facilities
from siren_web.services.supply_matrix import clear_facility_trace, set_facility_trace

class Command(BaseCommand):
    help = 'Load supply factors data from a CSV file into the SupplyFactorMatrix'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            default='swis_load_hourly_2024_for_sam.csv',
            help='CSV file path (default: swis_load_hourly_2024_for_sam.csv)'
        )
        parser.add_argument(
            '--facility-id',
            type=int,
            default=144,
            help='Facility ID to use for all records (default: 144)'
        )
        parser.add_argument(
            '--year',
            type=int,
            default=2024,
            help='Year to use for all records (default: 2024)'
        )
        parser.add_argument(
            '--clear-existing',
            action='store_true',
            help='Clear this facility/year in the matrix before loading new data'
        )

    def handle(self, *args, **options):
        file_path = options['file']
        facility_id = options['facility_id']
        year = options['year']
        clear_existing = options['clear_existing']

        # Check if file exists
        if not os.path.exists(file_path):
            raise CommandError(f'File "{file_path}" does not exist.')

        # Verify facility exists
        try:
            facility = facilities.objects.get(idfacilities=facility_id)
            self.stdout.write(
                self.style.SUCCESS(f'Found facility: {facility.facility_name} (ID: {facility_id})')
            )
        except facilities.DoesNotExist:
            raise CommandError(f'Facility with ID {facility_id} does not exist.')

        # Clear existing matrix data if requested
        if clear_existing:
            clear_facility_trace(year, facility_id)
            self.stdout.write(
                self.style.WARNING(f'Cleared existing matrix trace for facility {facility_id}, year {year}')
            )

        # Read and process CSV file
        hour_values = {}

        try:
            with open(file_path, 'r', newline='', encoding='utf-8') as csvfile:
                # Since there's no header, we'll read line by line
                reader = csv.reader(csvfile)
                # Skip the header row
                next(reader, None)

                for hour, row in enumerate(reader):
                    if not row or not row[0].strip():
                        self.stdout.write(
                            self.style.WARNING(f'Skipping empty row at hour {hour}')
                        )
                        continue

                    try:
                        quantum_value = float(row[0].strip())
                    except ValueError:
                        self.stdout.write(
                            self.style.ERROR(f'Invalid quantum value at row {hour}: {row[0]}')
                        )
                        continue

                    hour_values[hour] = quantum_value

                    # Show progress every 1000 records
                    if (hour + 1) % 1000 == 0:
                        self.stdout.write(f'Processed {hour + 1} records...')

        except Exception as e:
            raise CommandError(f'Error reading CSV file: {str(e)}')

        if not hour_values:
            raise CommandError('No valid records found in the CSV file.')

        # Gaps from skipped (empty/invalid) source lines become NaN in the
        # matrix rather than silently compacting the trace.
        max_hour = max(hour_values)
        trace = [hour_values.get(h, float('nan')) for h in range(max_hour + 1)]

        try:
            set_facility_trace(year, facility_id, trace)
        except Exception as e:
            raise CommandError(f'Error saving matrix trace: {str(e)}')

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully loaded {len(hour_values)} supply factor records.'
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f'Data loaded for facility {facility_id} ({facility.facility_name}), year {year}'
            )
        )

        # Summary statistics
        self.stdout.write('\n--- Summary ---')
        self.stdout.write(f'Records created: {len(hour_values)}')
        self.stdout.write(f'Hour range: 0 to {max_hour}')
        quantum_values = list(hour_values.values())
        self.stdout.write(f'Quantum value range: {min(quantum_values):.2f} to {max(quantum_values):.2f}')
        self.stdout.write(f'Average quantum value: {sum(quantum_values) / len(quantum_values):.2f}')
