from django.core.management.base import BaseCommand

from siren_web.models import FacilityScada
from siren_web.services.facility_scada_matrix import set_scada_values


class Command(BaseCommand):
    help = (
        "Backfill FacilityScadaMatrix from the existing row-per-(facility, "
        "interval) facility_scada table. Safe to re-run -- it only "
        "overwrites the intervals present in facility_scada, one year at a time."
    )

    def handle(self, *args, **options):
        years = sorted({d.year for d in FacilityScada.objects.dates('dispatch_interval', 'year')})

        if not years:
            self.stdout.write(self.style.WARNING("No facility_scada rows found -- nothing to backfill"))
            return

        total = 0
        for year in years:
            records = list(
                FacilityScada.objects.filter(dispatch_interval__year=year)
                .values('facility_id', 'dispatch_interval', 'quantity')
            )
            set_scada_values(records)
            total += len(records)
            self.stdout.write(self.style.SUCCESS(f"{year}: packed {len(records):,} intervals"))

        self.stdout.write(self.style.SUCCESS(f"Done -- {total:,} intervals backfilled into FacilityScadaMatrix"))
