"""
Demand Projection Utilities for Siren_web
Handles hour-by-hour demand projections for operational and underlying demand
"""
import numpy as np
from typing import Dict, List, Tuple
import pandas as pd

class DemandProjector:
    """Projects electricity demand based on base year hourly data and growth factors."""
    
    GROWTH_TYPES = ['linear', 'exponential', 's_curve', 'compound']
    
    def __init__(self, config_section: Dict):
        """
        Initialize projector with config section.
        
        Args:
            config_section: Dictionary from config file demand projection section
        """
        self.base_year = int(config_section.get('base_year', 2024))
        self.operational_growth_rate = float(config_section.get('operational_growth_rate', 0.02))
        self.underlying_growth_rate = float(config_section.get('underlying_growth_rate', 0.03))
        self.operational_growth_type = config_section.get('operational_growth_type', 'exponential')
        self.underlying_growth_type = config_section.get('underlying_growth_type', 'exponential')
        
        # S-curve parameters (if applicable)
        self.operational_saturation = float(config_section.get('operational_saturation', 2.0))
        self.underlying_saturation = float(config_section.get('underlying_saturation', 3.0))
        self.operational_midpoint = int(config_section.get('operational_midpoint_year', 2035))
        self.underlying_midpoint = int(config_section.get('underlying_midpoint_year', 2040))
    
    @staticmethod
    def apply_growth(base_demand: np.ndarray, years_ahead: int, 
                     growth_rate: float, growth_type: str,
                     saturation: float = 2.0, midpoint_year: int = 2035, 
                     base_year: int = 2024) -> np.ndarray:
        """
        Apply growth factor to hourly demand array.
        
        Args:
            base_demand: Numpy array of 8760 hourly demand values (MWh)
            years_ahead: Number of years to project forward
            growth_rate: Annual growth rate (e.g., 0.03 for 3%)
            growth_type: One of 'linear', 'exponential', 's_curve', 'compound'
            saturation: Maximum growth multiplier for s_curve
            midpoint_year: Year where s_curve reaches 50% of saturation
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
            # Exponential growth: demand * (1 + rate)^years
            growth_factor = (1 + growth_rate) ** years_ahead
            
        elif growth_type == 's_curve':
            # Logistic/S-curve growth for technology adoption
            # Factor ranges from 1 to saturation value
            midpoint_offset = midpoint_year - base_year
            k = growth_rate * 10  # Steepness parameter
            
            # Logistic function: 1 + (saturation - 1) / (1 + exp(-k * (year - midpoint)))
            growth_factor = 1 + (saturation - 1) / (
                1 + np.exp(-k * (years_ahead - midpoint_offset))
            )
            
        elif growth_type == 'compound':
            # Compound annual growth rate
            growth_factor = (1 + growth_rate) ** years_ahead
            
        else:
            raise ValueError(f"Unknown growth_type: {growth_type}")
        
        return base_demand * growth_factor
    
    def project_demand(self, base_operational: np.ndarray, 
                       base_underlying: np.ndarray,
                       target_year: int) -> Tuple[np.ndarray, np.ndarray]:
        """
        Project both operational and underlying demand to target year.
        
        Args:
            base_operational: Base year operational demand (8760 hours)
            base_underlying: Base year underlying demand (8760 hours)
            target_year: Year to project to
            
        Returns:
            Tuple of (projected_operational, projected_underlying) arrays
        """
        years_ahead = target_year - self.base_year
        
        if years_ahead < 0:
            raise ValueError(f"Target year {target_year} is before base year {self.base_year}")
        
        # Project operational demand
        proj_operational = self.apply_growth(
            base_operational, 
            years_ahead,
            self.operational_growth_rate,
            self.operational_growth_type,
            self.operational_saturation,
            self.operational_midpoint,
            self.base_year
        )
        
        # Project underlying demand
        proj_underlying = self.apply_growth(
            base_underlying,
            years_ahead,
            self.underlying_growth_rate,
            self.underlying_growth_type,
            self.underlying_saturation,
            self.underlying_midpoint,
            self.base_year
        )
        
        return proj_operational, proj_underlying
    
    def project_multiple_years(self, base_operational: np.ndarray,
                               base_underlying: np.ndarray,
                               year_range: List[int]) -> Dict[int, Dict]:
        """
        Project demand for multiple years.
        
        Args:
            base_operational: Base year operational demand
            base_underlying: Base year underlying demand
            year_range: List of years to project
            
        Returns:
            Dictionary keyed by year with operational and underlying projections
        """
        results = {}
        
        for year in year_range:
            proj_op, proj_und = self.project_demand(
                base_operational, base_underlying, year
            )
            
            results[year] = {
                'operational': proj_op,
                'underlying': proj_und,
                'total': proj_op + proj_und,
                'operational_total_mwh': proj_op.sum(),
                'underlying_total_mwh': proj_und.sum(),
                'total_mwh': (proj_op + proj_und).sum(),
                'operational_peak_mw': proj_op.max(),
                'underlying_peak_mw': proj_und.max(),
                'total_peak_mw': (proj_op + proj_und).max()
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
            summary_data.append({
                'Year': year,
                'Operational_Total_GWh': data['operational_total_mwh'] / 1000,
                'Underlying_Total_GWh': data['underlying_total_mwh'] / 1000,
                'Total_GWh': data['total_mwh'] / 1000,
                'Operational_Peak_MW': data['operational_peak_mw'],
                'Underlying_Peak_MW': data['underlying_peak_mw'],
                'Total_Peak_MW': data['total_peak_mw']
            })
        
        return pd.DataFrame(summary_data)


class ScenarioComparator:
    """Compare multiple demand projection scenarios."""
    
    def __init__(self, base_operational: np.ndarray, base_underlying: np.ndarray,
                 base_year: int):
        """
        Initialize scenario comparator.
        
        Args:
            base_operational: Base year operational demand
            base_underlying: Base year underlying demand
            base_year: Base year for projections
        """
        self.base_operational = base_operational
        self.base_underlying = base_underlying
        self.base_year = base_year
    
    def create_scenario(self, name: str, config: Dict) -> Tuple[str, DemandProjector]:
        """
        Create a named scenario with specific config.
        
        Args:
            name: Scenario name
            config: Configuration dictionary for the scenario
            
        Returns:
            Tuple of (name, DemandProjector)
        """
        config['base_year'] = str(self.base_year)
        projector = DemandProjector(config)
        return name, projector
    
    def compare_scenarios(self, scenarios: Dict[str, Dict], 
                         year_range: List[int]) -> Dict[str, Dict]:
        """
        Run multiple scenarios and return results.
        
        Args:
            scenarios: Dict of {scenario_name: config_dict}
            year_range: Years to project
            
        Returns:
            Dict of {scenario_name: projections}
        """
        results = {}
        
        for name, config in scenarios.items():
            _, projector = self.create_scenario(name, config)
            results[name] = projector.project_multiple_years(
                self.base_operational,
                self.base_underlying,
                year_range
            )
        
        return results