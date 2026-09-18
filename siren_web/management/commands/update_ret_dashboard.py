# management/commands/update_ret_dashboard.py
"""
Django management command to update renewable energy dashboard data
Can be run via cron job: python manage.py update_ret_dashboard
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime, timedelta
from calendar import monthrange
import logging

from siren_web.models import (
    MonthlyREPerformance, DailyPeakRE,
    NewCapacityCommissioned, facilities,
)
from siren_web.services.dpv_matrix import values_for_datetime_range
from siren_web.services.facility_scada_matrix import facility_matrix_for_datetime_range
from siren_web.services.wholesale_price_matrix import values_for_datetime_range as price_values_for_datetime_range
import numpy as np

logger = logging.getLogger(__name__)

# Price spike threshold ($/MWh)
PRICE_SPIKE_THRESHOLD = 300.0


class Command(BaseCommand):
    help = 'Update renewable energy dashboard data from SCADA'

    def add_arguments(self, parser):
        parser.add_argument(
            '--year',
            type=int,
            help='Specific year to update (default: last complete month)',
        )
        parser.add_argument(
            '--month',
            type=int,
            help='Specific month to update (1-12)',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force update even if data already exists',
        )
        parser.add_argument(
            '--ytd',
            action='store_true',
            help='Update all months year-to-date',
        )

    def handle(self, *args, **options):
        """Main command handler"""

        # Determine which period to update
        if options['year'] and options['month']:
            year = options['year']
            month = options['month']
            self.stdout.write(f"Updating specific period: {month}/{year}")
            self.update_month(year, month, options['force'])
            
        elif options['ytd']:
            # Update all months in current year
            year = options['year'] or timezone.now().year
            current_month = timezone.now().month
            self.stdout.write(f"Updating YTD for {year}")
            
            for month in range(1, current_month + 1):
                self.update_month(year, month, options['force'])
                
        else:
            # Default: update last complete month
            now = timezone.now()
            if now.day < 5:
                # If early in month, update previous month
                target_date = (now.replace(day=1) - timedelta(days=1))
            else:
                # Update last month
                target_date = (now.replace(day=1) - timedelta(days=1))
            
            year = target_date.year
            month = target_date.month
            
            self.stdout.write(f"Updating last complete month: {month}/{year}")
            self.update_month(year, month, options['force'])
        
        self.stdout.write(self.style.SUCCESS('Successfully updated RE dashboard data'))

    def update_month(self, year, month, force=False):
        """Update data for a specific month"""
        
        # Check if data already exists
        existing = MonthlyREPerformance.objects.filter(
            year=year, month=month
        ).first()
        
        if existing and not force:
            self.stdout.write(
                self.style.WARNING(
                    f"  Data for {month}/{year} already exists. Use --force to overwrite."
                )
            )
            return
        
        self.stdout.write(f"  Processing {month}/{year}...")
        
        # Get date range for the month
        _, last_day = monthrange(year, month)
        start_datetime = timezone.make_aware(datetime(year, month, 1, 0, 0, 0))
        end_datetime = timezone.make_aware(datetime(year, month, last_day, 23, 59, 59))
        end_exclusive = start_datetime + timedelta(days=last_day)

        # Load the month's slice of the packed SCADA matrix
        facility_ids, matrix = facility_matrix_for_datetime_range(start_datetime, end_exclusive)

        if matrix.size == 0 or np.all(np.isnan(matrix)):
            self.stdout.write(
                self.style.ERROR(
                    f"  No SCADA data found for {month}/{year}"
                )
            )
            return

        self.stdout.write(f"  Found {int(np.count_nonzero(~np.isnan(matrix))):,} SCADA records")

        facility_meta = self._facility_meta(facility_ids)

        # Calculate generation by fuel type
        generation_data = self.calculate_generation(facility_ids, matrix, facility_meta)

        # Get rooftop solar from DPVGeneration
        rooftop_solar = self.get_rooftop_solar(year, month, start_datetime, end_datetime)
        generation_data['solar_rooftop'] = rooftop_solar
        self.stdout.write(f"  Rooftop solar: {rooftop_solar:.1f} GWh")

        # Calculate total operational demand from SCADA
        operational_demand = generation_data['operational_demand']

        # Calculate emissions using facility emission intensities
        emissions_data = self.calculate_emissions(facility_ids, matrix, facility_meta)

        # Get peak/minimum demand
        peak_min_data = self.get_peak_minimum(matrix, start_datetime)

        # Get best RE hour (based on operational demand, excludes rooftop solar)
        best_re_hour = self.calculate_best_re_hour(matrix, facility_ids, facility_meta, start_datetime)

        # Get 5-minute peak instantaneous RE% from DailyPeakRE (calculated during SCADA fetch)
        five_min_peak = self.get_5min_peak_re(year, month)

        # Determine peak instantaneous RE%
        peak_inst_pct = five_min_peak.get('percentage')
        peak_inst_dt = five_min_peak.get('datetime')

        # Fallback: if no DailyPeakRE data or peak is invalid, use best single half-hour
        best_re_hour_pct = best_re_hour.get('percentage')
        if peak_inst_pct is None or (
            best_re_hour_pct is not None and peak_inst_pct < best_re_hour_pct
        ):
            if peak_inst_pct is not None and best_re_hour_pct is not None:
                self.stdout.write(self.style.WARNING(
                    f"  WARNING: peak_instantaneous ({peak_inst_pct:.1f}%) < "
                    f"best_re_hour ({best_re_hour_pct:.1f}%). Using single-interval fallback."
                ))
            half_hourly_peak = self.calculate_best_single_interval_re(matrix, facility_ids, facility_meta, start_datetime)
            peak_inst_pct = half_hourly_peak.get('percentage')
            peak_inst_dt = half_hourly_peak.get('datetime')

        # Get wholesale price statistics
        wholesale_data = self.calculate_wholesale_prices(year, month, start_datetime, end_datetime)

        # Calculate underlying demand (operational + rooftop)
        underlying_demand = operational_demand + rooftop_solar

        # Create or update record
        performance, created = MonthlyREPerformance.objects.update_or_create(
            year=year,
            month=month,
            defaults={
                'total_generation': operational_demand,
                'operational_demand': operational_demand,
                'underlying_demand': underlying_demand,
                'wind_generation': generation_data['wind'],
                'solar_generation': generation_data['solar_utility'],
                'dpv_generation': rooftop_solar,
                'biomass_generation': generation_data['biomass'],
                'gas_generation': generation_data.get('gas', 0),
                'coal_generation': generation_data.get('coal', 0),
                'storage_discharge': generation_data.get('storage_discharge', 0),
                'storage_charge': generation_data.get('storage_charge', 0),
                'hydro_discharge': generation_data.get('hydro_discharge', 0),
                'hydro_charge': generation_data.get('hydro_charge', 0),
                'total_emissions_tonnes': emissions_data['total_emissions'],
                'emissions_intensity_kg_kwh': emissions_data['emissions_intensity'],
                'peak_demand_mw': peak_min_data.get('peak_mw'),
                'peak_demand_datetime': peak_min_data.get('peak_datetime'),
                'minimum_demand_mw': peak_min_data.get('min_mw'),
                'minimum_demand_datetime': peak_min_data.get('min_datetime'),
                'best_re_hour_percentage': best_re_hour_pct,
                'best_re_hour_datetime': best_re_hour.get('datetime'),
                'peak_instantaneous_re_percentage': peak_inst_pct,
                'peak_instantaneous_re_datetime': peak_inst_dt,
                # Wholesale price fields
                'wholesale_price_max': wholesale_data.get('max_price'),
                'wholesale_price_max_datetime': wholesale_data.get('max_datetime'),
                'wholesale_price_min': wholesale_data.get('min_price'),
                'wholesale_price_min_datetime': wholesale_data.get('min_datetime'),
                'wholesale_price_avg': wholesale_data.get('avg_price'),
                'wholesale_price_std_dev': wholesale_data.get('std_dev'),
                'wholesale_negative_count': wholesale_data.get('negative_count'),
                'wholesale_spike_count': wholesale_data.get('spike_count'),
                'data_complete': True,
                'data_source': 'SCADA',
            }
        )
        
        action = "Created" if created else "Updated"
        re_pct = performance.re_percentage_underlying
        
        # Build output message
        msg = f"  {action} record: {month}/{year} - RE%: {re_pct:.1f}%, Emissions: {emissions_data['total_emissions']:.0f}t"
        if wholesale_data.get('avg_price') is not None:
            msg += f", Avg Price: ${wholesale_data['avg_price']:.2f}/MWh"
            if wholesale_data.get('negative_count', 0) > 0:
                msg += f", Neg intervals: {wholesale_data['negative_count']}"
            if wholesale_data.get('spike_count', 0) > 0:
                msg += f", Spikes: {wholesale_data['spike_count']}"
        
        self.stdout.write(self.style.SUCCESS(msg))
        
        # Update new capacity commissioned
        self.update_new_capacity(year, month)

    def _facility_meta(self, facility_ids):
        """
        Return {facility_id: {fuel_type, technology_name, category,
        emission_intensity, tech_emissions}} for the given facility ids,
        fuel_type/category upper-cased -- the metadata needed to replicate
        the old `.values('facility__idtechnologies__...')` grouping against
        a facility-id-keyed matrix instead of a queryset.
        """
        meta = {}
        for f in facilities.objects.filter(idfacilities__in=facility_ids).select_related('idtechnologies'):
            tech = f.idtechnologies
            meta[f.idfacilities] = {
                'fuel_type': (tech.fuel_type or '').upper() if tech else '',
                'technology_name': tech.technology_name or '' if tech else '',
                'category': (tech.category or '').upper() if tech else '',
                'emission_intensity': f.emission_intensity,
                'tech_emissions': tech.emissions if tech else None,
            }
        return meta

    def calculate_wholesale_prices(self, year, month, start_datetime, end_datetime):
        """
        Calculate wholesale price statistics for the month.
        
        Returns dict with:
            - max_price: Maximum wholesale price ($/MWh)
            - max_datetime: DateTime of maximum price
            - min_price: Minimum wholesale price ($/MWh)
            - min_datetime: DateTime of minimum price
            - avg_price: Average wholesale price ($/MWh)
            - std_dev: Standard deviation of prices ($/MWh)
            - negative_count: Number of intervals with negative prices
            - spike_count: Number of intervals with prices > $300/MWh
        """
        result = {
            'max_price': None,
            'max_datetime': None,
            'min_price': None,
            'min_datetime': None,
            'avg_price': None,
            'std_dev': None,
            'negative_count': None,
            'spike_count': None,
        }
        
        # Pull the month's half-hourly prices from the packed matrix
        # (end_datetime is the month's last second, 23:59:59 -- compute the
        # true exclusive end for the matrix lookup).
        _, last_day = monthrange(year, month)
        end_exclusive = start_datetime + timedelta(days=last_day)
        values = price_values_for_datetime_range(start_datetime, end_exclusive)
        present = values[~np.isnan(values)]

        if present.size == 0:
            self.stdout.write(
                self.style.WARNING(
                    f"  No wholesale price data found for {month}/{year}"
                )
            )
            return result

        record_count = present.size
        self.stdout.write(f"  Found {record_count} wholesale price records")

        # Django's StdDev() is the population standard deviation (ddof=0),
        # matching numpy's default.
        result['avg_price'] = float(np.mean(present))
        result['max_price'] = float(np.max(present))
        result['min_price'] = float(np.min(present))
        result['std_dev'] = float(np.std(present))
        result['negative_count'] = int(np.sum(present < 0))
        result['spike_count'] = int(np.sum(present > PRICE_SPIKE_THRESHOLD))

        # np.nanargmax/argmin return the first occurrence on ties, matching
        # the old .order_by('trading_interval').first() tie-break.
        result['max_datetime'] = start_datetime + timedelta(minutes=30 * int(np.nanargmax(values)))
        result['min_datetime'] = start_datetime + timedelta(minutes=30 * int(np.nanargmin(values)))
        
        # Log summary
        self.stdout.write(
            f"  Wholesale prices: "
            f"Min ${result['min_price']:.2f}, "
            f"Avg ${result['avg_price']:.2f} (±${result['std_dev']:.2f}), "
            f"Max ${result['max_price']:.2f}"
        )
        if result['negative_count'] > 0 or result['spike_count'] > 0:
            self.stdout.write(
                f"  Price events: "
                f"{result['negative_count']} negative intervals, "
                f"{result['spike_count']} spike intervals (>${PRICE_SPIKE_THRESHOLD})"
            )
        
        return result

    def calculate_generation(self, facility_ids, matrix, facility_meta):
        """Calculate generation totals by technology fuel type from the SCADA matrix.

        FacilityScada.quantity (packed into the matrix as-is) is ENERGY
        (MWh) already, summed by _aggregate_to_half_hourly() from AEMO's
        genuine 5-minute mWh readings -- not an instantaneous MW power
        reading. Confirmed 2026-08-19 against live AEMO data (see
        compute_annual_demand_actuals.py's module docstring for the
        verification). So a per-facility SUM across intervals is already
        MWh -- no further * 0.5.
        """

        generation: dict[str, float] = {
            'operational_demand': 0,
            'wind': 0,
            'solar_utility': 0,
            'solar_rooftop': 0,  # Will be filled from DPVGeneration
            'biomass': 0,
            'gas': 0,
            'coal': 0,
            'storage_discharge': 0,
            'storage_charge': 0,
            'hydro_discharge': 0,
            'hydro_charge': 0,
        }

        def _is_storage(fuel_type, category, tech_name):
            return category == 'STORAGE' or 'BATTERY' in tech_name.upper()

        with np.errstate(invalid='ignore'):
            discharge = np.where(matrix > 0, matrix, 0.0)
            charge = np.where(matrix < 0, matrix, 0.0)
        # Per-facility row totals (MWh) -- NaN cells already zeroed above.
        facility_discharge_totals = np.sum(discharge, axis=1)
        facility_charge_totals = np.sum(charge, axis=1)

        for i, fid in enumerate(facility_ids):
            meta = facility_meta.get(fid, {})
            fuel_type = meta.get('fuel_type', '')
            tech_name = meta.get('technology_name', '')
            category = meta.get('category', '')

            # total_mw is already a sum of half-hourly MWh values -- just
            # convert to GWh, no further * 0.5.
            gen_gwh = float(facility_discharge_totals[i]) / 1000.0

            if fuel_type == 'WIND':
                generation['wind'] += gen_gwh
            elif fuel_type == 'SOLAR':
                generation['solar_utility'] += gen_gwh
            elif fuel_type in ['BIOMASS', 'LANDFILL_GAS', 'BIOGAS']:
                generation['biomass'] += gen_gwh
            elif fuel_type in ['GAS', 'NATURAL_GAS', 'DISTILLATE']:
                generation['gas'] += gen_gwh
            elif fuel_type == 'COAL':
                generation['coal'] += gen_gwh
            elif fuel_type == 'HYDRO':
                generation['hydro_discharge'] += gen_gwh
            elif _is_storage(fuel_type, category, tech_name):
                generation['storage_discharge'] += gen_gwh

            charge_gwh = abs(float(facility_charge_totals[i])) / 1000.0

            if fuel_type == 'HYDRO':
                generation['hydro_charge'] += charge_gwh
            elif _is_storage(fuel_type, category, tech_name):
                generation['storage_charge'] += charge_gwh

        # Calculate total operational demand (all grid-connected generation)
        generation['operational_demand'] = (
            generation['wind'] +
            generation['solar_utility'] +
            generation['biomass'] +
            generation['gas'] +
            generation['coal'] +
            generation['hydro_discharge'] +
            generation['storage_discharge']
        )

        return generation

    def get_rooftop_solar(self, year, month, start_datetime, end_datetime):
        """Get rooftop solar generation from DPVGenerationMatrix"""

        # end_datetime is the month's last second (23:59:59); compute the
        # true exclusive end (start of next month) for the matrix lookup.
        _, last_day = monthrange(year, month)
        end_exclusive = start_datetime + timedelta(days=last_day)

        values = values_for_datetime_range(start_datetime, end_exclusive)

        if values.size == 0 or np.all(np.isnan(values)):
            self.stdout.write(
                self.style.WARNING(
                    f"  No DPV data found for {month}/{year}"
                )
            )
            return 0

        # Sum all estimated generation (in MW) for 30-minute intervals
        total_mw = np.nansum(values)

        if total_mw:
            # Convert from MW to GWh
            # Each reading is MW average over 30 minutes (0.5 hours)
            # So: (MW * 0.5 hours) / 1000 = GWh per interval
            # Sum of all intervals gives total GWh
            total_gwh = float(total_mw) * 0.5 / 1000.0
            return total_gwh

        return 0

    def calculate_emissions(self, facility_ids, matrix, facility_meta):
        """Calculate total emissions using facility emission intensities.

        Falls back to the related technology's emissions value when a facility
        has no emission_intensity set.

        Units:
          Facilities.emission_intensity : t CO2-e/MWh  (= kg CO2-e/kWh numerically)
          Technologies.emissions        : kg CO2-e/kWh
        Result intensity is returned in kg CO2-e/kWh.

        FacilityScada.quantity is already half-hourly ENERGY (MWh) -- see
        calculate_generation()'s docstring. sum(quantity) is already MWh,
        no further * 0.5.

        Per-facility totals here give the same result as the old grouped-
        by-intensity query: since the grouping key there WAS the intensity
        value itself, summing per facility and applying its own intensity
        is the same linear combination, just computed per row instead of
        per group.
        """

        total_emissions_kg = 0
        total_generation_kwh = 0

        facility_totals = np.nansum(matrix, axis=1)

        for i, fid in enumerate(facility_ids):
            total_mw = float(facility_totals[i])

            # total_mw is already MWh; convert to kWh.
            generation_kwh = total_mw * 1000

            if generation_kwh > 0:
                meta = facility_meta.get(fid, {})
                facility_intensity = meta.get('emission_intensity')
                tech_emissions = meta.get('tech_emissions')

                if facility_intensity is not None:
                    # t CO2-e/MWh == kg CO2-e/kWh; use value directly
                    emissions_kg = generation_kwh * float(facility_intensity)
                    total_emissions_kg += emissions_kg
                elif tech_emissions is not None:
                    # kg CO2-e/kWh; use directly
                    emissions_kg = generation_kwh * float(tech_emissions)
                    total_emissions_kg += emissions_kg

            total_generation_kwh += generation_kwh

        # Convert kg to tonnes
        total_emissions_tonnes = total_emissions_kg / 1000.0

        # Average emissions intensity in kg CO2-e/kWh
        if total_generation_kwh > 0:
            emissions_intensity = total_emissions_kg / total_generation_kwh
        else:
            emissions_intensity = 0

        return {
            'total_emissions': total_emissions_tonnes,
            'emissions_intensity': emissions_intensity  # kg CO2-e/kWh
        }

    def get_peak_minimum(self, matrix, start_utc):
        """Get peak and minimum operational demand (positive generation only, excludes charging)"""
        if matrix.shape[1] == 0:
            return {
                'peak_mw': None,
                'peak_datetime': None,
                'min_mw': None,
                'min_datetime': None,
            }

        with np.errstate(invalid='ignore'):
            positive = np.where(matrix > 0, matrix, 0.0)
        totals = np.sum(positive, axis=0)  # per-interval total demand (MWh)

        peak_idx = int(np.argmax(totals))
        min_idx = int(np.argmin(totals))

        # totals is sum of facility half-hourly ENERGY (MWh) for the
        # interval, not power. Average MW for the half hour = MWh / 0.5h.
        return {
            'peak_mw': float(totals[peak_idx]) * 2,
            'peak_datetime': start_utc + timedelta(minutes=30 * peak_idx),
            'min_mw': float(totals[min_idx]) * 2,
            'min_datetime': start_utc + timedelta(minutes=30 * min_idx),
        }

    def _re_row_mask(self, facility_ids, facility_meta):
        """Boolean mask over facility_ids: fuel_type in WIND/SOLAR/BIOMASS/HYDRO, or category=Storage (BESS)."""
        return np.array([
            facility_meta.get(fid, {}).get('fuel_type') in ('WIND', 'SOLAR', 'BIOMASS', 'HYDRO')
            or facility_meta.get(fid, {}).get('category') == 'STORAGE'
            for fid in facility_ids
        ])

    def calculate_best_re_hour(self, matrix, facility_ids, facility_meta, start_utc):
        """
        Calculate the interval with highest RE percentage based on operational demand.

        Operational RE% = (wind + solar + biomass + hydro discharge + battery discharge)
                          / operational demand
        Excludes rooftop solar (DPV) as that's not part of operational/grid demand.
        """
        best_re = {
            'percentage': None,
            'datetime': None
        }

        if matrix.shape[1] < 2:
            return best_re

        re_mask = self._re_row_mask(facility_ids, facility_meta)
        with np.errstate(invalid='ignore'):
            positive = np.where(matrix > 0, matrix, 0.0)
        total_gen = np.sum(positive, axis=0)
        re_gen = np.sum(positive[re_mask, :], axis=0) if re_mask.any() else np.zeros_like(total_gen)

        # Best Renewable Hour - average RE% over pairs of consecutive
        # half-hourly intervals (i.e. full clock hours). Matrix columns are
        # always exactly 30 minutes apart by construction, so every
        # adjacent pair is a real consecutive pair (no gap check needed).
        hourly_re = re_gen[:-1] + re_gen[1:]
        hourly_total = total_gen[:-1] + total_gen[1:]
        with np.errstate(invalid='ignore', divide='ignore'):
            hourly_pct = np.where(hourly_total > 0, (hourly_re / hourly_total) * 100, -np.inf)

        if np.any(hourly_total > 0):
            best_idx = int(np.argmax(hourly_pct))
            best_re['percentage'] = float(hourly_pct[best_idx])
            best_re['datetime'] = start_utc + timedelta(minutes=30 * best_idx)

        return best_re

    def calculate_best_single_interval_re(self, matrix, facility_ids, facility_meta, start_utc):
        """
        Calculate the single half-hourly interval with highest operational RE%.

        Used as fallback when DailyPeakRE (5-minute) data is unavailable.
        Always >= best_re_hour (which averages over paired half-hours).
        """
        best = {'percentage': None, 'datetime': None}

        if matrix.shape[1] == 0:
            return best

        re_mask = self._re_row_mask(facility_ids, facility_meta)
        with np.errstate(invalid='ignore'):
            positive = np.where(matrix > 0, matrix, 0.0)
        total_gen = np.sum(positive, axis=0)
        re_gen = np.sum(positive[re_mask, :], axis=0) if re_mask.any() else np.zeros_like(total_gen)

        if np.any(total_gen > 0):
            with np.errstate(invalid='ignore', divide='ignore'):
                pct = np.where(total_gen > 0, (re_gen / total_gen) * 100, -np.inf)
            best_idx = int(np.argmax(pct))
            best['percentage'] = float(pct[best_idx])
            best['datetime'] = start_utc + timedelta(minutes=30 * best_idx)

            self.stdout.write(
                f"  Best single-interval RE%: {best['percentage']:.1f}% "
                f"at {best['datetime']}"
            )

        return best

    def get_5min_peak_re(self, year, month):
        """
        Get peak 5-minute instantaneous operational RE% for a month
        from DailyPeakRE records (populated during SCADA fetch).
        """
        _, last_day = monthrange(year, month)
        start_date = datetime(year, month, 1).date()
        end_date = datetime(year, month, last_day).date()

        peak = DailyPeakRE.objects.filter(
            trading_date__gte=start_date,
            trading_date__lte=end_date
        ).order_by('-peak_re_percentage').first()

        if peak:
            self.stdout.write(
                f"  5-min peak RE%: {peak.peak_re_percentage:.1f}% "
                f"on {peak.peak_re_datetime}"
            )
            return {
                'percentage': peak.peak_re_percentage,
                'datetime': peak.peak_re_datetime,
            }
        return {}

    def update_new_capacity(self, year, month):
        """Update new capacity commissioned for the month"""
        
        # Find facilities commissioned in this month
        _, last_day = monthrange(year, month)
        start_date = datetime(year, month, 1).date()
        end_date = datetime(year, month, last_day).date()
        
        new_facilities = facilities.objects.filter(
            registered_from__gte=start_date,
            registered_from__lte=end_date,
            active=True
        ).select_related('idtechnologies')
        
        count = 0
        for facility in new_facilities:
            # Create commissioning record
            NewCapacityCommissioned.objects.get_or_create(
                facility=facility,
                commissioned_date=facility.registered_from,
                defaults={
                    'capacity_mw': facility.capacity or 0,
                    'technology_type': facility.idtechnologies.technology_name,
                    'report_year': year,
                    'report_month': month,
                    'status': 'commissioned',
                }
            )
            count += 1
        
        if count > 0:
            self.stdout.write(f"  Recorded {count} new facilities commissioned")