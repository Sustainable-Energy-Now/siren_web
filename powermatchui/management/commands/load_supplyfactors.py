# powermatchui/management/commands/load_supplyfactors.py
from decimal import Decimal
import os
import csv
from django.core.management.base import BaseCommand
from siren_web.models import Scenarios, supplyfactors, Zones
from siren_web.database_operations import fetch_technology_by_id

class Command(BaseCommand):
    help = 'Load supplyfactors from a CSV file'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Path to the CSV file')

    def handle(self, *args, **kwargs):
        csv_file_path = kwargs['csv_file']

        with open(csv_file_path, 'r') as file:
            reader = csv.DictReader(file)
            scenarios = Scenarios.objects.filter(
                pk=1
            ).all()
            zones = Zones.objects.filter(
                pk=1
            ).all()
            idTechnologies = fetch_technology_by_id('90')
            for row in reader:
                supplyfactors.objects.create(
                    idscenarios=scenarios[0],
                    idtechnologies=idTechnologies[0],
                    idzones=zones[0],
                    year=row['year'],
                    hour=row['hour'],
                    supply=row['supply'],
                    quantum=row['quantum'],
                    col=row['Col'],
                )
        self.stdout.write(self.style.SUCCESS('supplyfactors loaded successfully'))