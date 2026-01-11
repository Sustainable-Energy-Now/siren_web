"""
Capacity Factor Analyzer for Monte Carlo Simulations

This module analyzes historical renewable energy performance data to calculate
capacity factor distributions by technology for use in Monte Carlo simulations.

Capacity factors represent how much energy a facility actually produces compared
to its theoretical maximum, and vary year-to-year due to weather conditions.
"""

import logging
import numpy as np
import pandas as pd
from django.db.models import Sum, Avg, Count, Q
from datetime import datetime, date

logger = logging.getLogger(__name__)


class CapacityFactorAnalyzer:
    """
    Analyze historical capacity factors by technology from MonthlyREPerformance.

    Calculates statistical distributions (mean, std dev) for Monte Carlo sampling.
    """

    # Technology name mappings
    # Maps database technology names to standardized categories
    TECHNOLOGY_MAPPINGS = {
        'Wind': ['Wind', 'Onshore Wind', 'wind'],
        'Solar': ['Solar', 'Solar PV', 'Solar PV Fixed Tilt', 'Solar PV Tracking', 'solar'],
        'DPV': ['DPV', 'Distributed PV', 'Rooftop Solar', 'dpv'],
        'Biomass': ['Biomass', 'biomass'],
    }

    def __init__(self, start_year=None, end_year=None):
        """
        Initialize the analyzer with a date range for historical data.

        Args:
            start_year: int, starting year for analysis (default: 2 years ago)
            end_year: int, ending year for analysis (default: current year)
        """
        current_year = datetime.now().year

        self.start_year = start_year if start_year else (current_year - 2)
        self.end_year = end_year if end_year else current_year

        logger.info(f"Initialized CapacityFactorAnalyzer for period {self.start_year}-{self.end_year}")

    def calculate_technology_distributions(self):
        """
        Calculate CF mean and std dev by technology from historical data.

        Process:
        1. Query MonthlyREPerformance for date range
        2. Calculate monthly capacity factors by technology
        3. Group by technology and calculate statistics

        Returns:
            dict: {
                'Wind': {'mean': 0.35, 'std': 0.08, 'n_months': 24, 'min': 0.15, 'max': 0.50},
                'Solar': {'mean': 0.22, 'std': 0.05, 'n_months': 24, 'min': 0.10, 'max': 0.35},
                ...
            }
        """
        from siren_web.models import MonthlyREPerformance, facilities, FacilityWindTurbines, FacilitySolar

        logger.info("Calculating capacity factor distributions by technology...")

        # Query historical performance data
        performance_data = MonthlyREPerformance.objects.filter(
            year__gte=self.start_year,
            year__lte=self.end_year
        ).order_by('year', 'month')

        if not performance_data.exists():
            logger.warning(f"No MonthlyREPerformance data found for {self.start_year}-{self.end_year}")
            return self._get_default_distributions()

        # Convert to DataFrame for easier analysis
        df = pd.DataFrame(list(performance_data.values(
            'year', 'month',
            'wind_generation', 'solar_generation', 'dpv_generation', 'biomass_generation'
        )))

        logger.debug(f"Loaded {len(df)} months of performance data")

        # Get installed capacity by technology for each month
        # This is needed to calculate capacity factor = generation / (capacity × hours)
        distributions = {}

        # Calculate for each technology
        for tech in ['Wind', 'Solar', 'DPV', 'Biomass']:
            tech_dist = self._calculate_tech_distribution(df, tech)
            if tech_dist:
                distributions[tech] = tech_dist

        logger.info(f"Calculated distributions for {len(distributions)} technologies")
        for tech, dist in distributions.items():
            logger.info(f"  {tech}: mean={dist['mean']:.3f}, std={dist['std']:.3f}, n={dist['n_months']}")

        return distributions

    def _calculate_tech_distribution(self, df, technology):
        """
        Calculate capacity factor distribution for a specific technology.

        Args:
            df: DataFrame with monthly generation data
            technology: str, technology name ('Wind', 'Solar', 'DPV', 'Biomass')

        Returns:
            dict with mean, std, min, max, n_months
        """
        from siren_web.models import facilities, FacilityWindTurbines, FacilitySolar
        from calendar import monthrange

        # Map technology to generation column
        gen_column_map = {
            'Wind': 'wind_generation',
            'Solar': 'solar_generation',
            'DPV': 'dpv_generation',
            'Biomass': 'biomass_generation',
        }

        if technology not in gen_column_map:
            return None

        gen_column = gen_column_map[technology]

        # Get installed capacity for this technology
        # For simplicity, use average capacity over the period
        # In reality, capacity changes over time as facilities commission
        installed_capacity_mw = self._get_installed_capacity(technology)

        if installed_capacity_mw is None or installed_capacity_mw == 0:
            logger.warning(f"No installed capacity found for {technology}")
            return self._get_default_distribution_for_tech(technology)

        # Calculate monthly capacity factors
        capacity_factors = []

        for _, row in df.iterrows():
            generation_gwh = row[gen_column]

            if pd.isna(generation_gwh) or generation_gwh <= 0:
                continue

            # Calculate hours in this month
            year = int(row['year'])
            month = int(row['month'])
            days_in_month = monthrange(year, month)[1]
            hours_in_month = days_in_month * 24

            # Calculate capacity factor
            # CF = actual_generation_gwh / (capacity_mw * hours / 1000)
            theoretical_max_gwh = (installed_capacity_mw * hours_in_month) / 1000
            cf = generation_gwh / theoretical_max_gwh if theoretical_max_gwh > 0 else 0

            # Sanity check: CF should be between 0 and 1 (with some tolerance)
            if 0 <= cf <= 1.2:  # Allow up to 120% due to capacity additions mid-period
                capacity_factors.append(min(cf, 1.0))  # Cap at 100%

        if len(capacity_factors) < 3:  # Need at least 3 months of data
            logger.warning(f"Insufficient data for {technology} ({len(capacity_factors)} months)")
            return self._get_default_distribution_for_tech(technology)

        # Calculate statistics
        cf_array = np.array(capacity_factors)
        distribution = {
            'mean': float(np.mean(cf_array)),
            'std': float(np.std(cf_array)),
            'min': max(0.0, float(np.mean(cf_array) - 2 * np.std(cf_array))),  # 2 sigma lower bound
            'max': min(1.0, float(np.mean(cf_array) + 2 * np.std(cf_array))),  # 2 sigma upper bound
            'n_months': len(capacity_factors),
        }

        return distribution

    def _get_installed_capacity(self, technology):
        """
        Get average installed capacity for a technology during the analysis period.

        Args:
            technology: str, technology name

        Returns:
            float, capacity in MW
        """
        from siren_web.models import facilities, FacilityWindTurbines, FacilitySolar, NewCapacityCommissioned

        # For now, use a simplified approach: query NewCapacityCommissioned
        # for facilities that were commissioned before end_year
        # In future, could track capacity additions month-by-month

        capacity_data = NewCapacityCommissioned.objects.filter(
            technology_type__icontains=technology,
            status='commissioned',
            commissioned_date__lte=date(self.end_year, 12, 31)
        ).aggregate(total=Sum('capacity_mw'))

        total_capacity = capacity_data['total']

        if total_capacity:
            logger.debug(f"Found {total_capacity:.1f} MW of commissioned {technology} capacity")
            return float(total_capacity)

        # Fallback: use hardcoded estimates based on SWIS typical values
        fallback_capacity = {
            'Wind': 1200.0,  # MW (approximate SWIS wind capacity as of 2024)
            'Solar': 800.0,   # MW (utility-scale solar)
            'DPV': 2500.0,    # MW (rooftop solar - grows over time)
            'Biomass': 50.0,  # MW (small biomass plants)
        }

        capacity = fallback_capacity.get(technology, 100.0)
        logger.warning(f"Using fallback capacity for {technology}: {capacity} MW")
        return capacity

    def _get_default_distribution_for_tech(self, technology):
        """
        Return default capacity factor distribution for a technology.

        Used when insufficient historical data is available.
        Based on typical Australian renewable energy capacity factors.

        Args:
            technology: str, technology name

        Returns:
            dict with mean, std, min, max, n_months
        """
        defaults = {
            'Wind': {'mean': 0.35, 'std': 0.08, 'min': 0.15, 'max': 0.50, 'n_months': 0},
            'Solar': {'mean': 0.22, 'std': 0.05, 'min': 0.10, 'max': 0.35, 'n_months': 0},
            'DPV': {'mean': 0.18, 'std': 0.04, 'min': 0.08, 'max': 0.28, 'n_months': 0},
            'Biomass': {'mean': 0.70, 'std': 0.10, 'min': 0.50, 'max': 0.90, 'n_months': 0},
        }

        return defaults.get(technology, {'mean': 0.30, 'std': 0.10, 'min': 0.10, 'max': 0.50, 'n_months': 0})

    def _get_default_distributions(self):
        """
        Return default distributions for all technologies.

        Returns:
            dict of default distributions
        """
        logger.warning("Using default capacity factor distributions (no historical data)")

        return {
            'Wind': self._get_default_distribution_for_tech('Wind'),
            'Solar': self._get_default_distribution_for_tech('Solar'),
            'DPV': self._get_default_distribution_for_tech('DPV'),
            'Biomass': self._get_default_distribution_for_tech('Biomass'),
        }

    def get_facility_technology_map(self):
        """
        Map facility codes to technology types for pipeline facilities.

        Used to assign capacity factors to facilities in the Monte Carlo simulation.

        Returns:
            dict: {facility_code: technology_type}
        """
        from siren_web.models import NewCapacityCommissioned

        facilities_df = NewCapacityCommissioned.objects.filter(
            expected_commissioning_date__lte=date(2040, 12, 31)
        ).values('facility__facility_code', 'technology_type')

        tech_map = {
            fac['facility__facility_code']: fac['technology_type']
            for fac in facilities_df
            if fac['facility__facility_code'] and fac['technology_type']
        }

        logger.debug(f"Created technology map for {len(tech_map)} facilities")

        return tech_map

    def normalize_technology_name(self, tech_name):
        """
        Normalize technology names to standard categories.

        Args:
            tech_name: str, raw technology name from database

        Returns:
            str, normalized technology name ('Wind', 'Solar', 'DPV', 'Biomass')
        """
        if not tech_name:
            return 'Unknown'

        tech_lower = tech_name.lower()

        for standard_name, variants in self.TECHNOLOGY_MAPPINGS.items():
            for variant in variants:
                if variant.lower() in tech_lower:
                    return standard_name

        # Default fallback
        if 'wind' in tech_lower:
            return 'Wind'
        elif 'solar' in tech_lower or 'pv' in tech_lower:
            return 'Solar'
        elif 'biomass' in tech_lower or 'bio' in tech_lower:
            return 'Biomass'
        else:
            return 'Unknown'

    def validate_distributions(self, distributions):
        """
        Validate capacity factor distributions are reasonable.

        Args:
            distributions: dict of technology distributions

        Raises:
            ValueError if distributions are invalid

        Returns:
            bool, True if valid
        """
        for tech, dist in distributions.items():
            if dist['mean'] < 0 or dist['mean'] > 1:
                raise ValueError(f"{tech} has invalid mean CF: {dist['mean']}")

            if dist['std'] < 0 or dist['std'] > 0.5:
                raise ValueError(f"{tech} has invalid std dev: {dist['std']}")

            if dist['min'] < 0 or dist['max'] > 1:
                raise ValueError(f"{tech} has invalid bounds: [{dist['min']}, {dist['max']}]")

            if dist['min'] >= dist['max']:
                raise ValueError(f"{tech} has min >= max: {dist['min']} >= {dist['max']}")

        logger.info("Capacity factor distributions validated successfully")
        return True