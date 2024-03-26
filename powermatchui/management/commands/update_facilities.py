# powermatchui/management/commands/update_facilities.py
from decimal import Decimal
import os
import csv
from django.core.management.base import BaseCommand
from siren_web.models import facilities, Scenarios, Technologies, Zones

class Command(BaseCommand):
    help = 'Updates facilities model from a CSV file'

    def handle(self, *args, **options):
        # Assuming the CSV file is named 'Facilities.csv' in the same directory as this script
        file_path = 'Facilities.csv'
        file_path = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'Facilities.csv')


        # Mapping column indexes to technology objects
        tech_mapping = {
            14: Technologies.objects.get(idtechnologies=14),
            16: Technologies.objects.get(idtechnologies=16)
        }


 # Get the Scenarios instance for the scenario_id
        
        # Open CSV file and read rows
        with open(file_path, 'r') as file:
            csv_reader = csv.reader(file)
            next(csv_reader)  # Skip header row
            zone_instance = Zones.objects.get(idzones=0)
            for row in csv_reader:
                quantum = Decimal()
                facility_name = row[0]
                tech = tech_mapping[int(row[1])]
                capacity = Decimal(row[2])
                capacityfactor = Decimal(row[3])
                generation = Decimal(row[4])
                transmitted = Decimal(0)
                latitude = float(0)
                longitude = float(0)
                facilities_instance = facilities()
                facilities_instance.facility_name = facility_name
                facilities_instance.idtechnologies = tech
                facilities_instance.idzones = zone_instance
                facilities_instance.capacity = capacity
                facilities_instance.capacityfactor = capacityfactor
                facilities_instance.generation = generation
                facilities_instance.transmitted = transmitted
                facilities_instance.latitude = latitude
                facilities_instance.longitude = longitude
                facilities_instance.save()
        self.stdout.write(self.style.SUCCESS('facilities updated successfully'))