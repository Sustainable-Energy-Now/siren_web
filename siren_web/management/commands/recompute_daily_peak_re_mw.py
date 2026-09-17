# siren_web/management/commands/recompute_daily_peak_re_mw.py
"""
One-off data fix for DailyPeakRE.re_generation_mw / total_generation_mw.

Background: powerplotui/services/aemo_scada_fetcher.py's
_calculate_daily_peak_re() and _calculate_half_hourly_peak_re() stored these
two fields as raw MWh energy sums mislabeled as MW (fixed in the same
change that adds this command). peak_re_percentage/peak_re_datetime were
never wrong -- RE% is a ratio, so it's unaffected by the MWh-vs-MW mix-up --
only the two diagnostic MW fields need correcting.

The original raw 5-minute AEMO readings that may have produced some of
these rows are not persisted anywhere, so an exact like-for-like recompute
of the original 5-minute instant isn't possible. Instead, for each existing
DailyPeakRE row this recomputes re_generation_mw/total_generation_mw from
the half-hourly FacilityScada interval that contains peak_re_datetime
(quantity is half-hourly ENERGY in MWh -- see
compute_annual_demand_actuals.py's module docstring -- so average MW for
that half hour is quantity * 2). peak_re_percentage and peak_re_datetime
are left untouched.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Q

from siren_web.models import DailyPeakRE, facilities
from siren_web.services.facility_scada_matrix import cell_counts_for_datetime_range, total_for_datetime_range

RE_CONDITION = (
    Q(idtechnologies__fuel_type__in=['WIND', 'SOLAR', 'BIOMASS', 'HYDRO']) |
    Q(idtechnologies__category__iexact='storage')
)


class Command(BaseCommand):
    help = (
        'Recompute DailyPeakRE.re_generation_mw/total_generation_mw from half-hourly '
        'FacilityScada data (fixing the pre-existing MWh-labeled-as-MW bug). '
        'peak_re_percentage and peak_re_datetime are left unchanged.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Report what would change without writing to the database',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        rows = DailyPeakRE.objects.all().order_by('trading_date')

        re_facility_ids = list(facilities.objects.filter(RE_CONDITION).values_list('idfacilities', flat=True))

        updated = 0
        missing_interval = 0
        unchanged = 0

        for row in rows:
            dt = row.peak_re_datetime
            half_hour_start = dt.replace(
                minute=(dt.minute // 30) * 30, second=0, microsecond=0
            )
            half_hour_end = half_hour_start + timedelta(minutes=30)

            present = cell_counts_for_datetime_range(half_hour_start, half_hour_end)
            if present.size == 0 or present[0] == 0:
                missing_interval += 1
                self.stdout.write(
                    f"  No FacilityScada data at {half_hour_start} for "
                    f"{row.trading_date} -- leaving row unchanged"
                )
                continue

            total_mwh = float(total_for_datetime_range(half_hour_start, half_hour_end, positive_only=True)[0])
            re_mwh = float(total_for_datetime_range(
                half_hour_start, half_hour_end, facility_ids_wanted=re_facility_ids, positive_only=True,
            )[0])
            new_re_mw = re_mwh * 2
            new_total_mw = total_mwh * 2

            if (
                abs(new_re_mw - row.re_generation_mw) < 1e-6
                and abs(new_total_mw - row.total_generation_mw) < 1e-6
            ):
                unchanged += 1
                continue

            self.stdout.write(
                f"  {row.trading_date}: re_generation_mw "
                f"{row.re_generation_mw:.2f} -> {new_re_mw:.2f}, "
                f"total_generation_mw {row.total_generation_mw:.2f} -> {new_total_mw:.2f}"
            )

            if not dry_run:
                row.re_generation_mw = new_re_mw
                row.total_generation_mw = new_total_mw
                row.save(update_fields=['re_generation_mw', 'total_generation_mw'])

            updated += 1

        self.stdout.write(self.style.SUCCESS(
            f"{'Would update' if dry_run else 'Updated'} {updated} row(s); "
            f"{unchanged} already correct; {missing_interval} skipped (no matching SCADA interval)"
        ))
