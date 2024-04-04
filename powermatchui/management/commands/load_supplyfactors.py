# powermatchui/management/commands/load_supplyfactors.py
from decimal import Decimal
import os
import csv
from django.core.management.base import BaseCommand
from siren_web.models import supplyfactors, Scenarios, Technologies, Zones
from siren_web.database_operations import fetch_technology_by_id

class Command(BaseCommand):
    help = 'Load supplyfactors from a CSV file'

    def handle(self, *args, **options):
        # Assuming the CSV file is in the same directory as this script
        csv_file_path = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'SupplyFactors.csv')

        scenario_id = 1
        supply = True
        demand_year = 2022
 # Get the Scenarios instance for the scenario_id
        scenario_inst = Scenarios.objects.get(idscenarios=scenario_id)
        zones0_inst = Zones.objects.get(
            pk=0
        )
        zones1_inst = Zones.objects.get(
            pk=1
        )
        # Open CSV file and read column headers
        with open(csv_file_path, 'r') as file:
            csv_reader = csv.reader(file)
            tech = {}
            # for column in range(1, 8):
            #     tech_name = csv_reader.fieldnames[column]
            #     tech[column] = Technologies.objects.filter(
            #         technology_name=tech_name
            #     )
            # next(csv_reader)  # Skip header row
            for row in csv_reader:
                if row[1] == 'Load':
                    for column in range(1, 8):
                        tech_name = row[column]
                        tech[column] = Technologies.objects.filter(
                            technology_name=tech_name
                        )
                else:
                    hour = int(row[0].replace(',', ''))
                    for column in range(1, 8):
                        if column < 6:
                            zones_inst = zones0_inst
                        else:
                            zones_inst = zones1_inst
                        quantum = Decimal(row[column].replace(',', ''))
                        supplyfactors.objects.create(
                            idscenarios=scenario_inst,
                            idtechnologies=tech[column][0],
                            idzones=zones_inst,
                            year=demand_year,
                            hour=hour,
                            supply=supply,
                            quantum=quantum,
                            col=column - 1,
                        )

        self.stdout.write(self.style.SUCCESS('supplyfactors loaded successfully'))