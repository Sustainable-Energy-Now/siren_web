# powermatchui/management/commands/update_facilities.py
import csv
from decimal import Decimal
from django.core.management.base import BaseCommand
from datetime import datetime
import requests
from siren_web.models import facilities, Scenarios, Technologies, Zones

class Command(BaseCommand):
    help = 'Updates facilities model from the AEMO data repository csv file'

    def handle(self, *args, **options):
        url = 'https://data.wa.aemo.com.au/public/public-data/datafiles/facilities/facilities.csv'
        try:
            response = requests.get(url)
            response.raise_for_status()  # Raise exception for bad status cod
            # Decode the content and create a CSV reader
            csv_content = response.content.decode('utf-8').splitlines()
            csv_reader = csv.DictReader(csv_content)
            
            facilities_created = 0
            facilities_updated = 0
            
            # Mapping column indexes to technology objects
            tech_mapping = {
                'Black coal': Technologies.objects.get(idtechnologies=1),
                'Battery (1hr)': Technologies.objects.get(idtechnologies=2),
                'Battery (2hr)': Technologies.objects.get(idtechnologies=3),
                'Battery (4hr)': Technologies.objects.get(idtechnologies=4),
                'Battery (8hr)': Technologies.objects.get(idtechnologies=5),
                'Biomass': Technologies.objects.get(idtechnologies=6),
                'Gas OCGT': Technologies.objects.get(idtechnologies=7),
                'PHES (24hr)': Technologies.objects.get(idtechnologies=8),
                'PHES (48hr)': Technologies.objects.get(idtechnologies=9),
                'Distillate': Technologies.objects.get(idtechnologies=10),
                'Fixed PV': Technologies.objects.get(idtechnologies=11),
                'Hydrogen': Technologies.objects.get(idtechnologies=12),
                'Rooftop PV': Technologies.objects.get(idtechnologies=13),
                'Single Axis PV': Technologies.objects.get(idtechnologies=14),
                'Offshore Wind': Technologies.objects.get(idtechnologies=15),
                'Onshore Wind': Technologies.objects.get(idtechnologies=16),
                'Concentrated Solar Thermal': Technologies.objects.get(idtechnologies=18),
                'Gas CCGT': Technologies.objects.get(idtechnologies=19),
                'Gas Recip': Technologies.objects.get(idtechnologies=20),
                'Battery (12hr)': Technologies.objects.get(idtechnologies=143),
                'Battery (24hr)': Technologies.objects.get(idtechnologies=144),
                'Nuclear (SMR)': Technologies.objects.get(idtechnologies=145),
                'Nuclear large-scale': Technologies.objects.get(idtechnologies=146),
                'Offshore Wind Floating': Technologies.objects.get(idtechnologies=147), 
            }
            zone_instance = Zones.objects.get(idzones=0)
            for row in csv_reader:
                if row['Balancing Status'] == 'Active':
                    # Clean and prepare data
                    bit = row['Facility Code'].split('_')
                    if (bit[-1] == 'WF1' or bit[-1] == 'WWF'):
                        tech = 'Onshore Wind'
                    elif (bit[-1] == 'G1' or bit[-1] == 'G2'):
                        tech = 'Black coal'
                    elif bit[-1] == 'CCG1P':
                        tech = 'Gas CCGT'
                    elif bit[-1] == 'PV1':
                        tech = 'Fixed PV'
                    elif bit[-1] == 'PLANT':
                        tech = 'Biomass'
                    else:
                        tech = 'Gas OCGT'
                    # Try to get existing facility or create new one
                    facility, created = facilities.objects.update_or_create(
                        facility_code= row['Facility Code'].strip(),
                        participant_code= row['Participant Code'].strip(),
                        registered_from= row['Registered From'][0:10],
                        idtechnologies=tech_mapping[tech],
                        defaults={
                            'active': True,
                            'idzones': zone_instance,
                            'capacityfactor': 1,
                            'generation': 0,
                            'transmitted': 0,
                        }
                    )
                    if created:
                        facilities_created += 1
                    else:
                        facilities_updated += 1     
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully processed facilities: {facilities_created} created, '
                    f'{facilities_updated} updated'
                )
            )
            
        except requests.RequestException as e:
            self.stdout.write(
                self.style.ERROR(f'Error fetching CSV file: {str(e)}')
            )
        except csv.Error as e:
            self.stdout.write(
                self.style.ERROR(f'Error parsing CSV file: {str(e)}')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Unexpected error: {str(e)}')
            )
