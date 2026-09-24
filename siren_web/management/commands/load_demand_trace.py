import csv
import os
from django.core.management.base import BaseCommand, CommandError
from siren_web.models import Demand
from siren_web.services.demand_matrix import clear_demand_trace, set_demand_trace

class Command(BaseCommand):
    help = 'Load a hand-built demand trace from a CSV file into DemandMatrix, against an existing Demand row'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            required=True,
            help='CSV file path (one quantum value per row, no header data beyond the header row)'
        )
        parser.add_argument(
            '--demand-id',
            type=int,
            required=True,
            help='Demand ID to use for all records'
        )
        parser.add_argument(
            '--year',
            type=int,
            required=True,
            help='Year to use for all records'
        )
        parser.add_argument(
            '--clear-existing',
            action='store_true',
            help='Clear this demand/year in the matrix before loading new data'
        )

    def handle(self, *args, **options):
        file_path = options['file']
        demand_id = options['demand_id']
        year = options['year']
        clear_existing = options['clear_existing']

        if not os.path.exists(file_path):
            raise CommandError(f'File "{file_path}" does not exist.')

        try:
            demand = Demand.objects.get(pk=demand_id)
            self.stdout.write(
                self.style.SUCCESS(f'Found demand: {demand.name} (ID: {demand_id})')
            )
        except Demand.DoesNotExist:
            raise CommandError(f'Demand with ID {demand_id} does not exist.')

        if clear_existing:
            clear_demand_trace(year, demand_id)
            self.stdout.write(
                self.style.WARNING(f'Cleared existing matrix trace for demand {demand_id}, year {year}')
            )

        hour_values = {}

        try:
            with open(file_path, 'r', newline='', encoding='utf-8') as csvfile:
                reader = csv.reader(csvfile)
                next(reader, None)  # header row

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
            set_demand_trace(year, demand_id, trace)
        except Exception as e:
            raise CommandError(f'Error saving matrix trace: {str(e)}')

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully loaded {len(hour_values)} demand trace records.'
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f'Data loaded for demand {demand_id} ({demand.name}), year {year}'
            )
        )

        self.stdout.write('\n--- Summary ---')
        self.stdout.write(f'Records created: {len(hour_values)}')
        self.stdout.write(f'Hour range: 0 to {max_hour}')
        quantum_values = list(hour_values.values())
        self.stdout.write(f'Quantum value range: {min(quantum_values):.2f} to {max(quantum_values):.2f}')
        self.stdout.write(f'Average quantum value: {sum(quantum_values) / len(quantum_values):.2f}')
