from django.core.management.base import BaseCommand

from siren_web.models import DPVGeneration
from siren_web.services.dpv_matrix import set_interval_values


class Command(BaseCommand):
    help = (
        "Backfill DPVGenerationMatrix from the existing row-per-interval "
        "dpv_generation table. Safe to re-run -- it only overwrites the "
        "intervals present in dpv_generation, in year-sized batches."
    )

    def handle(self, *args, **options):
        years = sorted({d.year for d in DPVGeneration.objects.dates('trading_date', 'year')})

        if not years:
            self.stdout.write(self.style.WARNING("No dpv_generation rows found -- nothing to backfill"))
            return

        total = 0
        for year in years:
            records = list(
                DPVGeneration.objects.filter(trading_date__year=year)
                .values('trading_date', 'interval_number', 'estimated_generation')
            )
            set_interval_values(records)
            total += len(records)
            self.stdout.write(self.style.SUCCESS(f"{year}: packed {len(records):,} intervals"))

        self.stdout.write(self.style.SUCCESS(f"Done -- {total:,} intervals backfilled into DPVGenerationMatrix"))
