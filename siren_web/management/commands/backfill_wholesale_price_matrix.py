from django.core.management.base import BaseCommand

from siren_web.models import WholesalePrice
from siren_web.services.wholesale_price_matrix import set_price_values


class Command(BaseCommand):
    help = (
        "Backfill WholesalePriceMatrix from the existing row-per-interval "
        "WholesalePrice table. Safe to re-run -- it only overwrites the "
        "intervals present in WholesalePrice."
    )

    def handle(self, *args, **options):
        # set_price_values buckets by trading_interval's own true-UTC year
        # (not trading_date, which is AEMO's AWST trading-day label and can
        # disagree with the UTC calendar year for a few hours around each
        # New Year), so the whole table can be passed through in one call.
        records = list(WholesalePrice.objects.values('trading_interval', 'wholesale_price'))

        if not records:
            self.stdout.write(self.style.WARNING("No WholesalePrice rows found -- nothing to backfill"))
            return

        set_price_values(records)
        self.stdout.write(self.style.SUCCESS(f"Done -- {len(records):,} intervals backfilled into WholesalePriceMatrix"))
