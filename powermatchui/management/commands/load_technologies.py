# powermatchui/management/commands/load_technologies.py
from decimal import Decimal
import os
import csv
from django.core.management.base import BaseCommand
from ...models import Technologies

class Command(BaseCommand):
    help = 'Load technologies from a CSV file'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Path to the CSV file')

    def handle(self, *args, **kwargs):
        csv_file_path = kwargs['csv_file']
        with open(csv_file_path, 'r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                Technologies.objects.create(
                    technology_name=row['technology_name'],
                    year=row['year'],
                    image=row['image'],
                    caption=row['caption'],
                    category=row['category'],
                    renewable=row['renewable'],
                    dispatchable=row['dispatchable'],
                    merit_order=row['merit_order'],
                    capex=row['capex'],
                    fom=row['FOM'],
                    vom=row['VOM'],
                    lifetime=row['lifetime'],
                    discount_rate=row['discount_rate'],
                    description=row['description'],
                    capacity=row['capacity'],
                    mult=row['mult'],
                    capacity_max=row['capacity_max'],
                    capacity_min=row['capacity_min'],
                    emissions=row['emissions'],
                    initial=row['initial'],
                    lcoe=row['lcoe'],
                    lcoe_cf=row['lcoe_cf']
                )
        self.stdout.write(self.style.SUCCESS('Technologies loaded successfully'))
Name,Capacity,Constraint,Emissions,Initial,Order,Capex,FOM,VOM,Fuel,Lifetime,Discount Rate