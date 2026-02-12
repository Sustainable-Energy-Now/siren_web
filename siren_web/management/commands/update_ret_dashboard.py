# management/commands/update_ret_dashboard.py
"""
Django management command to update renewable energy dashboard data
Can be run via cron job: python manage.py update_ret_dashboard
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Sum, F, Avg, Max, Min, StdDev, Count, Q, Case, When, Value, DecimalField
from datetime import datetime, timedelta
from calendar import monthrange
import logging

from siren_web.models import (
    MonthlyREPerformance,
    NewCapacityCommissioned, FacilityScada, facilities,
    DPVGeneration, WholesalePrice
)

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
        
        # Query SCADA data for the month
        scada_data = FacilityScada.objects.filter(
            dispatch_interval__gte=start_datetime,
            dispatch_interval__lte=end_datetime
        ).select_related('facility', 'facility__idtechnologies')
        
        if not scada_data.exists():
            self.stdout.write(
                self.style.ERROR(
                    f"  No SCADA data found for {month}/{year}"
                )
            )
            return
        
        self.stdout.write(f"  Found {scada_data.count()} SCADA records")
        
        # Calculate generation by fuel type
        generation_data = self.calculate_generation(scada_data)
        
        # Get rooftop solar from DPVGeneration
        rooftop_solar = self.get_rooftop_solar(year, month, start_datetime, end_datetime)
        generation_data['solar_rooftop'] = rooftop_solar
        self.stdout.write(f"  Rooftop solar: {rooftop_solar:.1f} GWh")
        
        # Calculate total operational demand from SCADA
        operational_demand = generation_data['operational_demand']
        
        # Calculate emissions using facility emission intensities
        emissions_data = self.calculate_emissions(scada_data)
        
        # Get peak/minimum demand
        peak_min_data = self.get_peak_minimum(scada_data)
        
        # Get best RE hour (based on operational demand, excludes rooftop solar)
        best_re_hour = self.calculate_best_re_hour(scada_data)
        
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
                'total_emissions_tonnes': emissions_data['total_emissions'],
                'emissions_intensity_kg_mwh': emissions_data['emissions_intensity'],
                'peak_demand_mw': peak_min_data.get('peak_mw'),
                'peak_demand_datetime': peak_min_data.get('peak_datetime'),
                'minimum_demand_mw': peak_min_data.get('min_mw'),
                'minimum_demand_datetime': peak_min_data.get('min_datetime'),
                'best_re_hour_percentage': best_re_hour.get('percentage'),
                'best_re_hour_datetime': best_re_hour.get('datetime'),
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
        
        # Query wholesale prices for the month
        price_data = WholesalePrice.objects.filter(
            trading_interval__gte=start_datetime,
            trading_interval__lte=end_datetime
        )
        
        if not price_data.exists():
            self.stdout.write(
                self.style.WARNING(
                    f"  No wholesale price data found for {month}/{year}"
                )
            )
            return result
        
        record_count = price_data.count()
        self.stdout.write(f"  Found {record_count} wholesale price records")
        
        # Calculate aggregate statistics using Django ORM
        aggregates = price_data.aggregate(
            avg_price=Avg('wholesale_price'),
            max_price=Max('wholesale_price'),
            min_price=Min('wholesale_price'),
            std_dev=StdDev('wholesale_price'),
            negative_count=Count('id', filter=Q(wholesale_price__lt=0)),
            spike_count=Count('id', filter=Q(wholesale_price__gt=PRICE_SPIKE_THRESHOLD))
        )
        
        result['avg_price'] = aggregates['avg_price']
        result['max_price'] = aggregates['max_price']
        result['min_price'] = aggregates['min_price']
        result['std_dev'] = aggregates['std_dev']
        result['negative_count'] = aggregates['negative_count']
        result['spike_count'] = aggregates['spike_count']
        
        # Find the datetime for max price
        if result['max_price'] is not None:
            max_record = price_data.filter(
                wholesale_price=result['max_price']
            ).order_by('trading_interval').first()
            if max_record:
                result['max_datetime'] = max_record.trading_interval
        
        # Find the datetime for min price
        if result['min_price'] is not None:
            min_record = price_data.filter(
                wholesale_price=result['min_price']
            ).order_by('trading_interval').first()
            if min_record:
                result['min_datetime'] = min_record.trading_interval
        
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

    def calculate_generation(self, scada_data):
        """Calculate generation totals by technology fuel type from SCADA data"""
        
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
        }
        
        # Aggregate generation by fuel type
        # Group by facility and sum quantities
        facility_totals = scada_data.values(
            'facility__idtechnologies__fuel_type',
            'facility__idtechnologies__technology_name',
            'facility__idtechnologies__category'
        ).annotate(
            total_mw=Sum(
                Case(
                    When(
                        quantity__gt=0,
                        then=F('quantity')
                    ),
                    default=Value(0),
                    output_field=DecimalField()
                )
            )
        )
        
        for item in facility_totals:
            fuel_type = item.get('facility__idtechnologies__fuel_type', '').upper() if item.get('facility__idtechnologies__fuel_type') else ''
            tech_name = item.get('facility__idtechnologies__technology_name', '') or ''
            category = item.get('facility__idtechnologies__category', '').upper() if item.get('facility__idtechnologies__category') else ''
            total_mw = float(item['total_mw'] or 0)
            
            # Convert from MW (hourly average) to GWh
            gen_gwh = total_mw / 1000.0
            
            # Categorize by fuel type
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
            elif category == 'STORAGE' or 'BATTERY' in tech_name.upper():
                # Battery can be positive (discharge) or negative (charge)
                if gen_gwh >= 0:
                    generation['storage_discharge'] += gen_gwh
                else:
                    generation['storage_charge'] += abs(gen_gwh)
        
        # Calculate total operational demand
        # Sum of all generation
        generation['operational_demand'] = (
            generation['wind'] +
            generation['solar_utility'] +
            generation['biomass'] +
            generation['gas'] +
            generation['coal'] +
            generation['storage_discharge']
        )
        
        return generation

    def get_rooftop_solar(self, year, month, start_datetime, end_datetime):
        """Get rooftop solar generation from DPVGeneration model"""
        
        # Query DPV generation for the month
        dpv_data = DPVGeneration.objects.filter(
            trading_interval__gte=start_datetime,
            trading_interval__lte=end_datetime
        )
        
        if not dpv_data.exists():
            self.stdout.write(
                self.style.WARNING(
                    f"  No DPV data found for {month}/{year}"
                )
            )
            return 0
        
        # Sum all estimated generation (in MW) for 30-minute intervals
        # DPV data is in 30-minute intervals, so we need to convert to GWh
        total_mw = dpv_data.aggregate(
            total=Sum('estimated_generation')
        )['total']
        
        if total_mw:
            # Convert from MW to GWh
            # Each reading is MW average over 30 minutes (0.5 hours)
            # So: (MW * 0.5 hours) / 1000 = GWh per interval
            # Sum of all intervals gives total GWh
            total_gwh = float(total_mw) * 0.5 / 1000.0
            return total_gwh
        
        return 0

    def calculate_emissions(self, scada_data):
        """Calculate total emissions using facility emission intensities"""
        
        # Calculate emissions from each facility
        # emission_intensity is in t CO2-e per MWh
        # quantity is in MW (average for the hour)
        
        total_emissions_kg = 0
        total_generation_mwh = 0
        
        # Aggregate by facility
        facility_totals = scada_data.values(
            'facility__emission_intensity'
        ).annotate(
            total_mw=Sum('quantity'),
            facility_id=F('facility')
        )
        
        for item in facility_totals:
            emission_intensity = item.get('facility__emission_intensity')
            total_mw = float(item['total_mw'] or 0)
            
            # Convert MW hours to MWh
            # Since we have hourly data, sum of MW = MWh
            generation_mwh = total_mw
            
            if emission_intensity and generation_mwh > 0:
                # Emissions = generation (MWh) * intensity (kg/MWh)
                emissions_kg = generation_mwh * float(emission_intensity*1000)  # Convert t to kg
                total_emissions_kg += emissions_kg
            
            total_generation_mwh += generation_mwh
        
        # Convert kg to tonnes
        total_emissions_tonnes = total_emissions_kg / 1000.0
        
        # Calculate average emissions intensity for the month
        if total_generation_mwh > 0:
            emissions_intensity = total_emissions_kg / total_generation_mwh
        else:
            emissions_intensity = 0
        
        return {
            'total_emissions': total_emissions_tonnes,
            'emissions_intensity': emissions_intensity  # kg CO2-e per MWh
        }

    def get_peak_minimum(self, scada_data):
        """Get peak and minimum operational demand (positive generation only, excludes charging)"""
        from django.db.models import Case, When, Value, DecimalField

        # Aggregate by dispatch_interval to get total demand per half-hour interval
        # Only count positive values (generation) to exclude storage charging
        hourly_demand = scada_data.values('dispatch_interval').annotate(
            total_demand=Sum(
                Case(
                    When(
                        quantity__gt=0,
                        then=F('quantity')
                    ),
                    default=Value(0),
                    output_field=DecimalField()
                )
            )
        ).order_by('dispatch_interval')
        
        if not hourly_demand:
            return {
                'peak_mw': None,
                'peak_datetime': None,
                'min_mw': None,
                'min_datetime': None,
            }
        
        # Find max and min
        peak = max(hourly_demand, key=lambda x: x['total_demand'])
        minimum = min(hourly_demand, key=lambda x: x['total_demand'])

        # total_demand is half-hourly MWh (sum of facility quantities per interval).
        # Convert to MW: MW = half-hourly MWh / 0.5 hours = value * 2
        return {
            'peak_mw': float(peak['total_demand']) * 2,
            'peak_datetime': peak['dispatch_interval'],
            'min_mw': float(minimum['total_demand']) * 2,
            'min_datetime': minimum['dispatch_interval'],
        }

    def calculate_best_re_hour(self, scada_data):
        """
        Calculate the hour with highest RE percentage based on operational demand.

        Operational RE% = (wind + utility solar + biomass + storage) / operational demand
        Excludes rooftop solar (DPV) as that's not part of operational/grid demand.
        """
        from django.db.models import Case, When, Value, DecimalField

        best_re = {
            'percentage': None,
            'datetime': None
        }

        # Use conditional aggregation to calculate RE vs total for each interval
        # This does all the work in the database
        hourly_stats = scada_data.values('dispatch_interval').annotate(
            # Sum of renewable generation (conditionally sum based on fuel type)
            re_generation=Sum(
                Case(
                    When(
                        facility__idtechnologies__fuel_type__in=['WIND', 'SOLAR', 'BIOMASS', 'BESS', 'HYDRO'],
                        quantity__gt=0,
                        then=F('quantity')
                    ),
                    default=Value(0),
                    output_field=DecimalField()
                )
            ),
            # Sum of all generation (operational demand) - positive values only to exclude charging
            total_generation=Sum(
                Case(
                    When(
                        quantity__gt=0,
                        then=F('quantity')
                    ),
                    default=Value(0),
                    output_field=DecimalField()
                )
            )
        ).order_by('dispatch_interval')

        # Find the hour with maximum RE percentage
        max_re_percentage = 0
        best_datetime = None

        for hour in hourly_stats:
            re_gen = float(hour['re_generation'] or 0)
            total_gen = float(hour['total_generation'] or 0)

            if total_gen > 0:
                re_percentage = (re_gen / total_gen) * 100

                if re_percentage > max_re_percentage:
                    max_re_percentage = re_percentage
                    best_datetime = hour['dispatch_interval']

        if best_datetime:
            best_re['percentage'] = max_re_percentage
            best_re['datetime'] = best_datetime

        return best_re

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