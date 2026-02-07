"""
Factor-Based Demand Projection for Siren_web
Handles demand projections broken down by growth factors (EV, Industrial, etc.)
Each factor has independent growth parameters and base demand percentage.
"""
import numpy as np
from typing import Dict, List, Tuple
import pandas as pd
from django.db.models import QuerySet


class FactorBasedProjector:
    """
    Projects electricity demand using multiple independent growth factors.

    Each factor represents a portion of base demand (as a percentage) that
    grows according to its own formula. Total demand = sum of all factors.

    Example:
        - EV Adoption: 5% of base operational demand, growing at 8% exponentially
        - Industrial: 30% of base operational demand, growing at 2% linearly
        - Residential: 20% of base underlying demand, growing via S-curve
    """

    GROWTH_TYPES = ['linear', 'exponential', 's_curve', 'compound']

    def __init__(self, factors_queryset: QuerySet, base_year: int):
        """
        Initialize projector with demand factors.

        Args:
            factors_queryset: QuerySet of DemandFactor model instances
            base_year: Starting year for projections
        """
        self.factors = list(factors_queryset.select_related('factor_type'))
        self.base_year = base_year

        # Validate factors
        self._validate_factors()

    def _validate_factors(self):
        """Validate that factors are configured correctly"""
        operational_total = sum(f.base_percentage_operational for f in self.factors if f.is_active)
        underlying_total = sum(f.base_percentage_underlying for f in self.factors if f.is_active)

        if operational_total > 110.0:
            raise ValueError(
                f"Total operational factor percentages exceed 110%: {operational_total:.1f}%"
            )
        if underlying_total > 110.0:
            raise ValueError(
                f"Total underlying factor percentages exceed 110%: {underlying_total:.1f}%"
            )

    def _get_growth_rate_for_year(self, factor, year: int) -> float:
        """
        Get growth rate for a specific year.
        Supports time-varying rates via JSON config.

        Args:
            factor: DemandFactor instance
            year: Target year

        Returns:
            Growth rate for that year
        """
        if factor.time_varying_config:
            # Find the most recent year <= target year in config
            years = sorted([int(y) for y in factor.time_varying_config.keys()])
            applicable_years = [y for y in years if y <= year]

            if applicable_years:
                most_recent_year = max(applicable_years)
                return float(factor.time_varying_config[str(most_recent_year)])

        # Fall back to fixed growth rate
        return factor.growth_rate

    @staticmethod
    def apply_growth(base_demand: np.ndarray, years_ahead: int,
                     growth_rate: float, growth_type: str,
                     saturation: float = 2.0, midpoint_year: int = 2035,
                     steepness: float = 0.5,
                     base_year: int = 2024) -> np.ndarray:
        """
        Apply growth factor to hourly demand array.

        Args:
            base_demand: Numpy array of 8760 hourly demand values (MW)
            years_ahead: Number of years to project forward
            growth_rate: Annual growth rate (e.g., 0.03 for 3%)
            growth_type: One of 'linear', 'exponential', 's_curve', 'compound'
            saturation: Maximum growth multiplier for s_curve
            midpoint_year: Year where s_curve reaches 50% of saturation
            steepness: S-curve steepness (higher = sharper transition)
            base_year: Starting year for calculations

        Returns:
            Projected demand array (8760 hourly values)
        """
        if years_ahead == 0:
            return base_demand.copy()

        if growth_type == 'linear':
            # Simple linear growth: demand * (1 + rate * years)
            growth_factor = 1 + (growth_rate * years_ahead)

        elif growth_type == 'exponential':
            # True continuous exponential growth: demand * e^(rate * years)
            growth_factor = np.exp(growth_rate * years_ahead)

        elif growth_type == 's_curve':
            # Logistic/S-curve growth for technology adoption
            # Normalized so growth_factor = 1.0 at years_ahead = 0
            midpoint_offset = midpoint_year - base_year
            k = steepness

            # Logistic function value at t and at t=0
            L_t = (saturation - 1) / (1 + np.exp(-k * (years_ahead - midpoint_offset)))
            L_0 = (saturation - 1) / (1 + np.exp(-k * (0 - midpoint_offset)))

            # Normalized: equals 1.0 at base year, approaches saturation at infinity
            growth_factor = 1 + L_t - L_0

        elif growth_type == 'compound':
            # Compound annual growth rate: demand * (1 + rate)^years
            growth_factor = (1 + growth_rate) ** years_ahead

        else:
            raise ValueError(f"Unknown growth_type: {growth_type}")

        return base_demand * growth_factor

    def _compute_time_varying_growth_factor(self, factor, target_year: int) -> float:
        """
        Compute cumulative growth factor for factors with time-varying rates.
        Accumulates growth year-by-year using the appropriate formula.

        Args:
            factor: DemandFactor instance with time_varying_config
            target_year: Year to project to

        Returns:
            Cumulative growth factor (float), or None for s_curve (use apply_growth instead)
        """
        if factor.growth_type == 's_curve':
            # S-curve shape is defined by saturation/midpoint/steepness,
            # not cumulative rates. Use apply_growth directly.
            return None

        growth_factor = 1.0
        for y in range(self.base_year + 1, target_year + 1):
            rate = self._get_growth_rate_for_year(factor, y)
            if factor.growth_type == 'linear':
                # Linear: add rate each year
                growth_factor += rate
            elif factor.growth_type == 'compound':
                # Compound: multiply by (1 + rate) each year
                growth_factor *= (1 + rate)
            elif factor.growth_type == 'exponential':
                # True exponential: multiply by e^rate each year
                growth_factor *= np.exp(rate)
        return growth_factor

    def _apply_factor_growth(self, base_demand: np.ndarray, factor,
                             target_year: int, years_ahead: int) -> np.ndarray:
        """
        Apply growth to a factor's base demand, handling both fixed and
        time-varying rates correctly.

        Args:
            base_demand: Base demand array for this factor (already scaled by percentage)
            factor: DemandFactor instance
            target_year: Year to project to
            years_ahead: Number of years from base year

        Returns:
            Projected demand array
        """
        if years_ahead == 0:
            return base_demand.copy()

        # Time-varying rates: accumulate year-by-year
        if factor.time_varying_config and factor.growth_type != 's_curve':
            cumulative_factor = self._compute_time_varying_growth_factor(factor, target_year)
            if cumulative_factor is not None:
                return base_demand * cumulative_factor

        # Fixed rate or S-curve: use apply_growth
        growth_rate = self._get_growth_rate_for_year(factor, target_year)
        return self.apply_growth(
            base_demand,
            years_ahead,
            growth_rate,
            factor.growth_type,
            factor.saturation_multiplier,
            factor.midpoint_year,
            factor.steepness,
            self.base_year
        )

    def project_with_factors(self, base_operational: np.ndarray,
                            base_underlying: np.ndarray,
                            target_year: int) -> Dict:
        """
        Project demand using factor breakdown.

        Each factor takes its percentage of base demand and applies its own growth.
        Total demand = sum of all factor demands.

        Args:
            base_operational: Base year operational demand (8760 hours, MW)
            base_underlying: Base year underlying demand (8760 hours, MW)
            target_year: Year to project to

        Returns:
            {
                'operational': {
                    'total': np.ndarray (8760 hours),
                    'factors': {
                        'EV Adoption': np.ndarray,
                        'Industrial': np.ndarray,
                        ...
                    }
                },
                'underlying': { ... },
                'total': np.ndarray (8760 hours),
                'metadata': {
                    'year': int,
                    'factor_count': int,
                    'operational_percentage_coverage': float,
                    'underlying_percentage_coverage': float
                }
            }
        """
        years_ahead = target_year - self.base_year

        if years_ahead < 0:
            raise ValueError(f"Target year {target_year} is before base year {self.base_year}")

        operational_factors = {}
        underlying_factors = {}
        operational_total_pct = 0.0
        underlying_total_pct = 0.0

        for factor in self.factors:
            if not factor.is_active:
                continue

            factor_name = factor.factor_type.name

            # PROJECT OPERATIONAL DEMAND FOR THIS FACTOR
            if factor.base_percentage_operational > 0:
                # Calculate base demand for this factor
                base_op_factor = base_operational * (factor.base_percentage_operational / 100.0)

                # Apply growth (handles both fixed and time-varying rates)
                proj_op_factor = self._apply_factor_growth(
                    base_op_factor, factor, target_year, years_ahead
                )

                operational_factors[factor_name] = proj_op_factor
                operational_total_pct += factor.base_percentage_operational

            # PROJECT UNDERLYING DEMAND FOR THIS FACTOR
            if factor.base_percentage_underlying > 0:
                # Calculate base demand for this factor
                base_und_factor = base_underlying * (factor.base_percentage_underlying / 100.0)

                # Apply growth (handles both fixed and time-varying rates)
                proj_und_factor = self._apply_factor_growth(
                    base_und_factor, factor, target_year, years_ahead
                )

                underlying_factors[factor_name] = proj_und_factor
                underlying_total_pct += factor.base_percentage_underlying

        # Sum all factors
        total_operational = sum(operational_factors.values()) if operational_factors else np.zeros(8760)
        total_underlying = sum(underlying_factors.values()) if underlying_factors else np.zeros(8760)

        return {
            'operational': {
                'total': total_operational,
                'factors': operational_factors
            },
            'underlying': {
                'total': total_underlying,
                'factors': underlying_factors
            },
            'total': total_operational + total_underlying,
            'metadata': {
                'year': target_year,
                'factor_count': len([f for f in self.factors if f.is_active]),
                'operational_percentage_coverage': operational_total_pct,
                'underlying_percentage_coverage': underlying_total_pct
            }
        }

    def project_multiple_years(self, base_operational: np.ndarray,
                               base_underlying: np.ndarray,
                               year_range: List[int]) -> Dict[int, Dict]:
        """
        Project demand for multiple years with factor breakdown.

        Args:
            base_operational: Base year operational demand
            base_underlying: Base year underlying demand
            year_range: List of years to project

        Returns:
            Dictionary keyed by year with projections and statistics:
            {
                2025: {
                    'operational': { 'total': array, 'factors': {...} },
                    'underlying': { 'total': array, 'factors': {...} },
                    'total': array,
                    'operational_total_mwh': float,
                    'operational_peak_mw': float,
                    'underlying_total_mwh': float,
                    'underlying_peak_mw': float,
                    'total_mwh': float,
                    'total_peak_mw': float,
                    'factor_breakdown_operational_gwh': {'EV': float, 'Industrial': float, ...},
                    'factor_breakdown_underlying_gwh': {...},
                    'metadata': {...}
                },
                2026: {...},
                ...
            }
        """
        results = {}

        for year in year_range:
            projection = self.project_with_factors(
                base_operational, base_underlying, year
            )

            # Calculate statistics
            operational_total = projection['operational']['total']
            underlying_total = projection['underlying']['total']
            total = projection['total']

            # Factor-level breakdown in GWh
            factor_breakdown_op_gwh = {
                name: demand.sum() / 1000  # Convert MWh to GWh
                for name, demand in projection['operational']['factors'].items()
            }

            factor_breakdown_und_gwh = {
                name: demand.sum() / 1000
                for name, demand in projection['underlying']['factors'].items()
            }

            results[year] = {
                'operational': projection['operational'],
                'underlying': projection['underlying'],
                'total': total,
                'operational_total_mwh': operational_total.sum(),
                'operational_peak_mw': operational_total.max(),
                'underlying_total_mwh': underlying_total.sum(),
                'underlying_peak_mw': underlying_total.max(),
                'total_mwh': total.sum(),
                'total_peak_mw': total.max(),
                'factor_breakdown_operational_gwh': factor_breakdown_op_gwh,
                'factor_breakdown_underlying_gwh': factor_breakdown_und_gwh,
                'metadata': projection['metadata']
            }

        return results

    def get_annual_summary(self, projections: Dict[int, Dict]) -> pd.DataFrame:
        """
        Create summary DataFrame of annual projections.

        Args:
            projections: Output from project_multiple_years

        Returns:
            DataFrame with annual statistics
        """
        summary_data = []

        for year, data in sorted(projections.items()):
            row = {
                'Year': year,
                'Operational_Total_GWh': data['operational_total_mwh'] / 1000,
                'Underlying_Total_GWh': data['underlying_total_mwh'] / 1000,
                'Total_GWh': data['total_mwh'] / 1000,
                'Operational_Peak_MW': data['operational_peak_mw'],
                'Underlying_Peak_MW': data['underlying_peak_mw'],
                'Total_Peak_MW': data['total_peak_mw'],
                'Factor_Count': data['metadata']['factor_count'],
                'Coverage_Operational_%': data['metadata']['operational_percentage_coverage'],
                'Coverage_Underlying_%': data['metadata']['underlying_percentage_coverage']
            }

            # Add per-factor operational breakdown
            for factor_name, gwh in data['factor_breakdown_operational_gwh'].items():
                row[f'{factor_name}_Op_GWh'] = gwh

            # Add per-factor underlying breakdown
            for factor_name, gwh in data['factor_breakdown_underlying_gwh'].items():
                row[f'{factor_name}_Und_GWh'] = gwh

            summary_data.append(row)

        return pd.DataFrame(summary_data)

    def get_factor_contributions(self, projections: Dict[int, Dict],
                                year: int, demand_type: str = 'total') -> Dict[str, float]:
        """
        Get percentage contribution of each factor for a specific year.

        Args:
            projections: Output from project_multiple_years
            year: Target year
            demand_type: 'operational', 'underlying', or 'total'

        Returns:
            {'EV Adoption': 15.5, 'Industrial': 32.1, ...}  # Percentages
        """
        if year not in projections:
            raise ValueError(f"Year {year} not in projections")

        data = projections[year]

        if demand_type == 'operational':
            total_gwh = data['operational_total_mwh'] / 1000
            breakdown = data['factor_breakdown_operational_gwh']
        elif demand_type == 'underlying':
            total_gwh = data['underlying_total_mwh'] / 1000
            breakdown = data['factor_breakdown_underlying_gwh']
        elif demand_type == 'total':
            total_gwh = data['total_mwh'] / 1000
            # Combine both operational and underlying
            breakdown = {}
            for name in set(list(data['factor_breakdown_operational_gwh'].keys()) +
                          list(data['factor_breakdown_underlying_gwh'].keys())):
                op_gwh = data['factor_breakdown_operational_gwh'].get(name, 0)
                und_gwh = data['factor_breakdown_underlying_gwh'].get(name, 0)
                breakdown[name] = op_gwh + und_gwh
        else:
            raise ValueError(f"demand_type must be 'operational', 'underlying', or 'total'")

        if total_gwh == 0:
            return {name: 0.0 for name in breakdown.keys()}

        # Calculate percentages
        return {
            name: (gwh / total_gwh) * 100
            for name, gwh in breakdown.items()
        }
