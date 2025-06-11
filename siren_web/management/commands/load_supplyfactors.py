import csv
import os
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from siren_web.models import supplyfactors, facilities

class Command(BaseCommand):
    help = 'Load supply factors data from CSV file into supplyfactors table'

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
            help='Clear existing records for the facility/year before loading new data'
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

        # Clear existing records if requested
        if clear_existing:
            deleted_count = supplyfactors.objects.filter(
                idfacilities=facility_id,
                year=year
            ).delete()[0]
            self.stdout.write(
                self.style.WARNING(f'Deleted {deleted_count} existing records for facility {facility_id}, year {year}')
            )

        # Read and process CSV file
        records_to_create = []
        
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
                    
                    # Create supply factor record
                    supply_factor = supplyfactors(
                        idfacilities=facility,
                        year=year,
                        hour=hour,
                        supply=0,
                        quantum=quantum_value
                    )
                    records_to_create.append(supply_factor)
                    
                    # Show progress every 1000 records
                    if (hour + 1) % 1000 == 0:
                        self.stdout.write(f'Processed {hour + 1} records...')

        except Exception as e:
            raise CommandError(f'Error reading CSV file: {str(e)}')

        if not records_to_create:
            raise CommandError('No valid records found in the CSV file.')

        # Bulk create records in a transaction
        try:
            with transaction.atomic():
                supplyfactors.objects.bulk_create(records_to_create, batch_size=1000)
                
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully loaded {len(records_to_create)} supply factor records.'
                )
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f'Data loaded for facility {facility_id} ({facility.facility_name}), year {year}'
                )
            )
            
        except Exception as e:
            raise CommandError(f'Error saving records to database: {str(e)}')

        # Summary statistics
        self.stdout.write('\n--- Summary ---')
        self.stdout.write(f'Records created: {len(records_to_create)}')
        self.stdout.write(f'Hour range: 0 to {len(records_to_create) - 1}')
        if records_to_create:
            quantum_values = [r.quantum for r in records_to_create]
            self.stdout.write(f'Quantum value range: {min(quantum_values):.2f} to {max(quantum_values):.2f}')
            self.stdout.write(f'Average quantum value: {sum(quantum_values) / len(quantum_values):.2f}')
