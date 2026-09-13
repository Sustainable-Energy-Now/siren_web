import itertools

import numpy as np
from django.core.management.base import BaseCommand

from siren_web.models import SupplyFactorMatrix, supplyfactors


class Command(BaseCommand):
    help = (
        'Backfill SupplyFactorMatrix rows from the legacy row-per-hour '
        '`supplyfactors` table. Safe to re-run: each year is rebuilt from '
        'scratch and upserted, so this can also be used to refresh a year '
        'after supplyfactors changes.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--year',
            type=int,
            help='Only backfill this year (default: all years present in supplyfactors)',
        )

    def handle(self, *args, **options):
        year_filter = options.get('year')

        years = [year_filter] if year_filter else list(
            supplyfactors.objects.values_list('year', flat=True).distinct().order_by('year')
        )

        if not years:
            self.stdout.write(self.style.WARNING('No supplyfactors rows found.'))
            return

        for year in years:
            self.build_year(year)

    def build_year(self, year):
        rows = (
            supplyfactors.objects
            .filter(year=year, idfacilities__isnull=False)
            .order_by('idfacilities', 'hour')
            .values_list('idfacilities', 'hour', 'quantum')
            .iterator(chunk_size=20000)
        )

        facility_ids = []
        facility_hour_maps = []
        max_hour = -1

        for fid, group in itertools.groupby(rows, key=lambda r: r[0]):
            hour_map = {}
            for _, hour, quantum in group:
                if hour is None:
                    continue
                hour_map[hour] = quantum
                if hour > max_hour:
                    max_hour = hour
            facility_ids.append(fid)
            facility_hour_maps.append(hour_map)

        if not facility_ids or max_hour < 0:
            self.stdout.write(self.style.WARNING(f'{year}: no usable rows, skipping'))
            return

        n_hours = max_hour + 1
        matrix = np.full((len(facility_ids), n_hours), np.nan, dtype='float32')
        for i, hour_map in enumerate(facility_hour_maps):
            for hour, quantum in hour_map.items():
                matrix[i, hour] = np.nan if quantum is None else quantum

        SupplyFactorMatrix.objects.update_or_create(
            year=year,
            defaults=dict(
                facility_ids=facility_ids,
                n_hours=n_hours,
                dtype='float32',
                data=matrix.tobytes(),
            ),
        )

        self.stdout.write(self.style.SUCCESS(
            f'{year}: built matrix for {len(facility_ids)} facilities x {n_hours} hours '
            f'({matrix.nbytes / 1024:.1f} KB)'
        ))
