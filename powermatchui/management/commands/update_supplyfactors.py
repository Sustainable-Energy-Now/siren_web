# powermatchui/management/commands/update_supplyfactors.py
from decimal import Decimal
import os
import csv
from django.core.management.base import BaseCommand
from siren_web.models import supplyfactors, Scenarios, Technologies, Zones

class Command(BaseCommand):
    help = 'Updates Supplyfactors model from a CSV file'

    def handle(self, *args, **options):
        # Assuming the CSV file is named 'data.csv' in the same directory as this script
        file_path = 'SupplyFactors0.csv'
        file_path = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'SupplyFactors1.csv')


        # Mapping column indexes to technology objects
        tech_mapping = {
            3: Technologies.objects.get(idtechnologies=17),
            4: Technologies.objects.get(idtechnologies=16),
            5: Technologies.objects.get(idtechnologies=11),
            6: Technologies.objects.get(idtechnologies=14),
            7: Technologies.objects.get(idtechnologies=16),
            8: Technologies.objects.get(idtechnologies=14)
        }

        scenario_id = 1
        supply = True
 # Get the Scenarios instance for the scenario_id
        scenario_instance = Scenarios.objects.get(idscenarios=scenario_id)
        # Open CSV file and read rows
        # tech = tech_mapping[column]
        # for column in range(1, 8):
        with open(file_path, 'r') as file:
            csv_reader = csv.reader(file)
            next(csv_reader)  # Skip header row
            # zone_instance_0 = Zones.objects.get(idzones=0)
            # zone_instance_1 = Zones.objects.get(idzones=1)
            tech = Technologies.objects.get(
                idtechnologies = 95
            )
            for row in csv_reader:
                hour = int(row[4].replace(',', ''))
                quantum = Decimal(row[6].replace(',', ''))
                # tech = tech_mapping[column]
                # if column < 7:
                #     zone_instance = zone_instance_0
                # else:
                #     zone_instance = zone_instance_1
                supplyfactors_instance = supplyfactors.objects.get(
                    idtechnologies=tech,
                    hour=hour
                )
                # supplyfactors_instance.idscenarios=scenario_instance
                # supplyfactors_instance.idtechnologies=tech
                # supplyfactors_instance.idzones=zone_instance
                # supplyfactors_instance.hour=hour
                # supplyfactors_instance.supply=supply
                supplyfactors_instance.quantum=quantum
                supplyfactors_instance.save()

        self.stdout.write(self.style.SUCCESS('Supplyfactors updated successfully'))