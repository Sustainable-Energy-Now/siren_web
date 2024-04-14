import openpyxl
from django.core.management.base import BaseCommand
from siren_web.models import supplyfactors, Scenarios, Technologies, Zones

class Command(BaseCommand):
    help = 'Loads supplyfactors model from an XLSX file'

    def add_arguments(self, parser):
        parser.add_argument('file_path', type=str, help='Path to the XLSX file')

    def handle(self, *args, **options):
        file_path = options['file_path']
        workbook = openpyxl.load_workbook(file_path)
        worksheet = workbook.active

        for row in worksheet.iter_rows(min_row=2, values_only=True):
            idscenarios_value = row[0]
            idtechnologies_value = row[1]
            idzones_value = row[2]
            year_value = row[3]
            hour_value = row[4] if row[4] is not None else None
            supply_value = row[5] if row[5] is not None else None
            quantum_value = row[6] if row[6] is not None else None
            col_value = row[7] if row[7] is not None else None

            scenario = Scenarios.objects.get(pk=idscenarios_value)
            technology = Technologies.objects.get(pk=idtechnologies_value)
            zone = Zones.objects.get(pk=idzones_value)

            supplyfactors.objects.create(
                idscenarios=scenario,
                idtechnologies=technology,
                idzones=zone,
                year=year_value,
                hour=hour_value,
                supply=supply_value,
                quantum=quantum_value,
                col=col_value
            )

        self.stdout.write(self.style.SUCCESS('Data loaded successfully'))