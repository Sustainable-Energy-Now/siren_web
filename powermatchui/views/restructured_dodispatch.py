# Restructured doDispatch() with proper merit order energy balancing
# Key changes:
# 1. _calculate_energy_balance now properly handles merit order dispatch
# 2. Storage is integrated into the hourly dispatch loop
# 3. Minimum capacity requirements are handled correctly
# 4. Curtailment is properly tracked

import numpy as np
import time
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from powermatchui.views.progress_handler import ProgressHandler

@dataclass
class Technology:
    def __init__(self, **kwargs):
        kwargs = {**kwargs}
        self.order = 0
        self.lifetime = 20
        self.area = None
        for attr in ['tech_name', 'tech_type', 'renewable', 'category', 'capacity', 'multiplier', 'capacity_max',
                     'capacity_min', 'lcoe', 'lcoe_cf', 'recharge_max', 'recharge_loss', 'min_runtime', 'warm_time',
                     'discharge_max', 'discharge_loss', 'parasitic_loss', 'emissions', 'initial','merit_order',
                     'capex', 'fixed_om', 'variable_om', 'fuel', 'lifetime', 'area', 'disc_rate']:
            setattr(self, attr, 0.)
        for key, value in kwargs.items():
            if value != '' and value is not None:
                if key == 'lifetime' and value == 0:
                    setattr(self, key, 20)
                else:
                    setattr(self, key, value)
                    
@dataclass
class DispatchResults:
    """Container for dispatch analysis results"""
    summary_data: np.ndarray
    hourly_data: Optional[np.ndarray]
    metadata: Dict[str, Any]

@dataclass
class EnergyBalance:
    """Container for energy balance calculations"""
    hourly_load: List[float]
    hourly_shortfall: List[float]
    hourly_surplus: List[float]
    hourly_curtailment: List[float]
    facility_generation: Dict[str, List[float]]
    facility_totals: Dict[str, float]
    correlation_data: Optional[List]

@dataclass
class StorageState:
    """Container for storage system state"""
    name: str
    capacity: float
    current_level: float
    min_level: float
    max_level: float
    charge_rate: float
    discharge_rate: float
    charge_efficiency: float
    discharge_efficiency: float
    parasitic_loss: float
    min_runtime: int
    warm_time: float
    # Operating state tracking
    discharge_run_active: bool = False
    warm_run_active: bool = False
    hours_in_discharge: int = 0

class PowerMatchProcessor:
    """Restructured PowerMatch processor with integrated merit order dispatch"""
    
    def __init__(self, config, scenarios, progress_handler: Optional[ProgressHandler] = None, 
                event_callback=None, status_callback=None):
        self.listener = progress_handler
        self.event_callback = event_callback  # UI passes its event-processing function
        self.setStatus = status_callback or (lambda text: None)  # Default to no-op
        self.carbon_price = 0.
        self.carbon_price_max = 200.
        self.discount_rate = 0.
        self.load_folder = ''
        self.optimise_choice = 'LCOE'
        self.optimise_generations = 20
        self.optimise_mutation = 0.005
        self.optimise_population = 50
        self.optimise_stop = 0
        self.optimise_default = None
        self.optimise_multiplot = True
        self.optimise_multisurf = False
        self.optimise_multitable = False
        self.optimise_to_batch = True
        self.remove_cost = True
        self.results_prefix = ''
        self.surplus_sign = 1
        self.underlying = ['Rooftop PV']
        self.operational = []
        self.show_correlation = False
    
    def doDispatch(self, year, option, sender_name, pmss_details, pmss_data
                   ) -> DispatchResults:
        """
        Main dispatch function with integrated merit order energy balancing
        """
        start_time = time.time()
        
        # Initialize processing
        config = self._initialize_dispatch(year, option, pmss_details)
        
        # Calculate energy balance with proper merit order dispatch
        energy_balance = self._calculate_energy_balance(pmss_details, pmss_data)
        
        # Calculate economic metrics
        economic_results = self._calculate_economics(energy_balance.facility_totals, pmss_details)
        
        # Generate summary statistics
        summary_stats = self._generate_summary_statistics(energy_balance, economic_results, config)
        
        # Create output arrays
        summary_array, hourly_array = self._create_output_arrays(summary_stats, option, config)
        
        # Compile metadata
        metadata = self._compile_metadata(
            start_time, year, option, sender_name, energy_balance, summary_stats, config
        )
        
        self._update_status(sender_name, time.time() - start_time)
        
        return DispatchResults(summary_array, hourly_array, metadata)
    
    def _initialize_dispatch(self, year, option, pmss_details) -> Dict:
        """Initialize dispatch configuration and parameters"""
        config = {
            'year': year,
            'option': option,
            'the_days': [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31],
            'sf_test': ['<', '>'] if self.surplus_sign >= 0 else ['>', '<'],
            'sf_sign': ['-', '+'] if self.surplus_sign >= 0 else ['+', '-'],
            'max_lifetime': self._calculate_max_lifetime(pmss_details),
            'underlying_facs': self._identify_underlying_facilities(pmss_details),
            'storage_names': [],
            'generator_names': [],
        }
        
        # Identify storage and generator facilities
        for tech_name, details in pmss_details.items():
            if tech_name == 'Load':
                continue
            if details.tech_type == 'S':  # Storage
                config['storage_names'].append(tech_name)
            elif details.tech_type == 'G':  # Generator
                config['generator_names'].append(tech_name)
        
        self._update_progress(6)
        return config
    
    def _calculate_max_lifetime(self, pmss_details) -> float:
        """Calculate maximum lifetime across all technologies"""
        max_lifetime = 0
        for key, details in pmss_details.items():
            if key in ['Load', 'Total']:
                continue
            if details.capacity * details.multiplier > 0:
                max_lifetime = max(max_lifetime, details.lifetime)
        return max_lifetime
    
    def _identify_underlying_facilities(self, pmss_details) -> List[str]:
        """Identify facilities that contribute to underlying load"""
        underlying_facs = []
        for tech_name, details in pmss_details.items():
            if tech_name == 'Load':
                continue
            if tech_name in self.operational:
                continue
            
            base_name = tech_name.split('.')[-1] if '.' in tech_name else tech_name
            if tech_name in self.underlying or base_name in self.underlying:
                underlying_facs.append(tech_name)
        
        return underlying_facs
    
    def _calculate_energy_balance(self, pmss_details, pmss_data) -> EnergyBalance:
        """
        Calculate hourly energy balance with proper merit order dispatch including storage
        """
        # Initialize tracking arrays
        hourly_load = []
        hourly_shortfall = []
        hourly_surplus = []
        hourly_curtailment = []
        facility_generation = {}
        facility_totals = {}
        
        # Get load data
        load_col = pmss_details['Load'].merit_order
        load_multiplier = pmss_details['Load'].multiplier
        
        # Initialize storage states
        storage_states = self._initialize_storage_states(pmss_details)
        
        # Initialize facility tracking
        for tech_name in pmss_details.keys():
            if tech_name != 'Load':
                facility_generation[tech_name] = []
                facility_totals[tech_name] = 0.0
        
        # Process each hour
        for h in range(8760):
            # Get hourly load
            load_h = pmss_data[load_col][h] * load_multiplier
            hourly_load.append(load_h)
            
            # Start with load as the remaining demand to meet
            remaining_demand = load_h
            hour_curtailment = 0.0
            
            # Apply parasitic losses to storage first
            for storage_state in storage_states:
                if storage_state.current_level > 0:
                    parasitic_loss = storage_state.current_level * storage_state.parasitic_loss / 24
                    storage_state.current_level = max(0, storage_state.current_level - parasitic_loss)
            
            # Process facilities in merit order (pmss_details should already be ordered)
            for tech_name, details in pmss_details.items():
                if tech_name == 'Load':
                    continue
                
                capacity = details.capacity * details.multiplier
                if capacity == 0:
                    facility_generation[tech_name].append(0)
                    continue
                
                hour_generation = 0.0
                
                if details.tech_type == 'S':  # Storage
                    hour_generation = self._dispatch_storage_hour(
                        tech_name, details, storage_states, remaining_demand, h
                    )
                    remaining_demand = max(0, remaining_demand - hour_generation)
                
                elif details.tech_type == 'G':  # Generator
                    hour_generation = self._dispatch_generator_hour(
                        tech_name, details, remaining_demand, h
                    )
                    remaining_demand = max(0, remaining_demand - hour_generation)
                
                else:  # Renewable (tech_type == 'R' or others)
                    available_generation = self._get_renewable_generation(
                        tech_name, details, pmss_data, h
                    )
                    
                    if remaining_demand > 0:
                        # Use what's needed to meet demand
                        hour_generation = min(available_generation, remaining_demand)
                        remaining_demand -= hour_generation
                        
                        # Curtail excess renewable
                        curtailed = available_generation - hour_generation
                        hour_curtailment += curtailed
                    else:
                        # All renewable is curtailed if no demand
                        hour_curtailment += available_generation
                        hour_generation = 0
                
                # Track generation
                facility_generation[tech_name].append(hour_generation)
                facility_totals[tech_name] += hour_generation
            
            # After all facilities dispatched, handle any excess capacity for storage charging
            if remaining_demand < 0:  # We have excess generation (should not happen with proper dispatch)
                excess = abs(remaining_demand)
                excess = self._charge_storage_systems(storage_states, excess)
                if excess > 0:
                    hour_curtailment += excess
                remaining_demand = 0
            
            # Handle any remaining excess renewable for storage charging
            if hour_curtailment > 0:
                charged_energy = self._charge_storage_systems(storage_states, hour_curtailment)
                hour_curtailment -= charged_energy
            
            # Record hourly results
            hourly_shortfall.append(remaining_demand)
            hourly_surplus.append(0 if remaining_demand > 0 else abs(remaining_demand))
            hourly_curtailment.append(hour_curtailment)
        
        # Calculate correlation if requested
        correlation_data = None
        if self.show_correlation:
            correlation_data = self._calculate_correlation(
                hourly_load, facility_generation, pmss_data, load_col
            )
        
        return EnergyBalance(
            hourly_load=hourly_load,
            hourly_shortfall=hourly_shortfall,
            hourly_surplus=hourly_surplus,
            hourly_curtailment=hourly_curtailment,
            facility_generation=facility_generation,
            facility_totals=facility_totals,
            correlation_data=correlation_data
        )
    
    def _initialize_storage_states(self, pmss_details) -> List[StorageState]:
        """Initialize storage system states"""
        storage_states = []
        
        for tech_name, details in pmss_details.items():
            if details.tech_type == 'S':  # Storage
                capacity = details.capacity * details.multiplier
                if capacity > 0:
                    storage_state = StorageState(
                        name=tech_name,
                        capacity=capacity,
                        current_level=details.initial * details.multiplier,
                        min_level=capacity * details.capacity_min,
                        max_level=capacity * details.capacity_max,
                        charge_rate=capacity * details.recharge_max,
                        discharge_rate=capacity * details.discharge_max,
                        charge_efficiency=1 - details.recharge_loss,
                        discharge_efficiency=1 - details.discharge_loss,
                        parasitic_loss=details.parasitic_loss,
                        min_runtime=int(details.min_runtime),
                        warm_time=details.warm_time
                    )
                    
                    # Initialize operating state
                    if storage_state.min_runtime > 0 and storage_state.current_level == 0:
                        storage_state.discharge_run_active = False
                    else:
                        storage_state.discharge_run_active = True
                    
                    storage_states.append(storage_state)
        
        return storage_states
    
    def _get_renewable_generation(self, tech_name, details, pmss_data, hour) -> float:
        """Get available renewable generation for this hour"""
        merit_order = details.merit_order
        if merit_order > 0 and merit_order in pmss_data:
            return pmss_data[merit_order][hour] * details.multiplier
        else:
            # Constant generation facility
            return details.capacity * details.multiplier
    
    def _dispatch_storage_hour(self, tech_name, details, storage_states, remaining_demand, hour) -> float:
        """Dispatch storage for one hour"""
        # Find this storage system
        storage_state = None
        for state in storage_states:
            if state.name == tech_name:
                storage_state = state
                break
        
        if not storage_state or remaining_demand <= 0:
            return 0.0
        
        # Check if storage can discharge
        available_energy = storage_state.current_level - storage_state.min_level
        if available_energy <= 0:
            return 0.0
        
        # Check minimum runtime requirements
        if storage_state.min_runtime > 0 and not storage_state.discharge_run_active:
            # Look ahead to see if we should start
            if self._should_start_discharge_run(storage_state, hour, remaining_demand):
                storage_state.discharge_run_active = True
                storage_state.hours_in_discharge = 0
            else:
                return 0.0
        
        # Calculate discharge amount
        energy_needed_from_storage = remaining_demand / storage_state.discharge_efficiency
        max_discharge = min(
            energy_needed_from_storage,
            available_energy,
            storage_state.discharge_rate
        )
        
        # Apply warm-up penalty if first hour of operation
        if storage_state.warm_time > 0 and not storage_state.warm_run_active:
            storage_state.warm_run_active = True
            max_discharge *= (1 - storage_state.warm_time)
        
        if max_discharge > 0:
            # Calculate actual energy delivered
            energy_delivered = max_discharge * storage_state.discharge_efficiency
            
            # Update storage level
            storage_state.current_level -= max_discharge
            
            # Update operating state
            storage_state.hours_in_discharge += 1
            
            return energy_delivered
        
        return 0.0
    
    def _should_start_discharge_run(self, storage_state, current_hour, current_demand) -> bool:
        """Check if storage should start a discharge run based on minimum runtime"""
        # Simple heuristic: start if current demand exists
        # In a more sophisticated version, this could look ahead at future hours
        return current_demand > 0
    
    def _dispatch_generator_hour(self, tech_name, details, remaining_demand, hour) -> float:
        """Dispatch generator for one hour"""
        if remaining_demand <= 0:
            return 0.0
        
        capacity = details.capacity * details.multiplier
        max_capacity = capacity * details.capacity_max if details.capacity_max > 0 else capacity
        min_capacity = capacity * details.capacity_min
        
        # Calculate generation
        if remaining_demand >= max_capacity:
            generation = max_capacity
        elif remaining_demand < min_capacity:
            generation = min_capacity  # Must run at minimum
        else:
            generation = remaining_demand
        
        return generation
    
    def _charge_storage_systems(self, storage_states, available_energy) -> float:
        """Charge storage systems with available excess energy"""
        charged_total = 0.0
        
        for storage_state in storage_states:
            if available_energy <= 0:
                break
            
            # Calculate available storage capacity
            available_capacity = storage_state.max_level - storage_state.current_level
            if available_capacity <= 0:
                continue
            
            # Calculate maximum charge considering efficiency
            max_charge_raw = available_capacity / storage_state.charge_efficiency
            max_charge = min(
                available_energy,
                max_charge_raw,
                storage_state.charge_rate
            )
            
            if max_charge > 0:
                # Calculate energy stored
                energy_stored = max_charge * storage_state.charge_efficiency
                
                # Update storage level
                storage_state.current_level += energy_stored
                
                # Reduce available energy
                available_energy -= max_charge
                charged_total += max_charge
                
                # Reset discharge run state
                storage_state.discharge_run_active = False
                storage_state.warm_run_active = False
                storage_state.hours_in_discharge = 0
        
        return charged_total
    
    def _calculate_correlation(self, hourly_load, facility_generation, pmss_data, load_col) -> List:
        """Calculate correlation between load and renewable generation"""
        try:
            # Calculate total renewable contribution
            total_renewable = []
            for h in range(len(hourly_load)):
                hour_renewable = 0
                for tech_name, generation_profile in facility_generation.items():
                    if h < len(generation_profile):
                        hour_renewable += generation_profile[h]
                total_renewable.append(hour_renewable)
            
            # Calculate correlation
            corr = np.corrcoef(hourly_load, total_renewable)
            if np.isnan(corr.item((0, 1))):
                corr_value = 0
            else:
                corr_value = corr.item((0, 1))
            
            return [['Correlation To Load'], ['RE Contribution', corr_value]]
        
        except Exception:
            return [['Correlation To Load'], ['RE Contribution', 0]]
    
    def _calculate_economics(self, facility_totals, pmss_details) -> Dict:
        """Calculate economic metrics for all facilities"""
        economic_results = {}
        
        for tech_name, annual_generation in facility_totals.items():
            if tech_name in pmss_details:
                details = pmss_details[tech_name]
                capacity = details.capacity * details.multiplier
                
                if capacity > 0:
                    economics = self._calculate_facility_economics(
                        capacity, annual_generation, details
                    )
                    economic_results[tech_name] = economics
        
        return economic_results
    
    def _calculate_facility_economics(self, capacity, annual_generation, details) -> Dict:
        """Calculate economic metrics for a single facility"""
        # Calculate LCOE based on cost structure
        if (details.capex > 0 or details.fixed_om > 0 or 
            details.variable_om > 0 or details.fuel > 0):
            
            # Full cost calculation
            capex = capacity * details.capex
            opex = (capacity * details.fixed_om + 
                   annual_generation * details.variable_om + 
                   annual_generation * details.fuel)
            
            disc_rate = details.disc_rate if details.disc_rate > 0 else self.discount_rate
            lcoe = self._calc_lcoe(annual_generation, capex, opex, disc_rate, details.lifetime)
            annual_cost = annual_generation * lcoe
            
            return {
                'lcoe': lcoe,
                'annual_cost': annual_cost,
                'capital_cost': capex,
                'capacity_factor': annual_generation / (capacity * 8760) if capacity > 0 else 0
            }
        
        elif details.lcoe > 0:
            # Reference LCOE calculation
            cf = details.lcoe_cf if details.lcoe_cf > 0 else (annual_generation / (capacity * 8760) if capacity > 0 else 0)
            annual_cost = details.lcoe * cf * 8760 * capacity
            
            return {
                'lcoe': details.lcoe,
                'annual_cost': annual_cost,
                'capital_cost': 0,
                'capacity_factor': cf
            }
        
        else:
            # No cost facility
            return {
                'lcoe': 0,
                'annual_cost': 0,
                'capital_cost': 0,
                'capacity_factor': annual_generation / (capacity * 8760) if capacity > 0 else 0
            }
    
    def _calc_lcoe(self, annual_output, capital_cost, annual_operating_cost, discount_rate, lifetime):
        """Calculate levelized cost of electricity"""
        if discount_rate > 0:
            annual_cost_capital = capital_cost * discount_rate * pow(1 + discount_rate, lifetime) / \
                                  (pow(1 + discount_rate, lifetime) - 1)
        else:
            annual_cost_capital = capital_cost / lifetime
        
        total_annual_cost = annual_cost_capital + annual_operating_cost
        
        try:
            return total_annual_cost / annual_output
        except ZeroDivisionError:
            return total_annual_cost
    
    def _generate_summary_statistics(self, energy_balance, economic_results, config) -> Dict:
        """Generate comprehensive summary statistics"""
        # Calculate totals
        total_load = sum(energy_balance.hourly_load)
        total_shortfall = sum(energy_balance.hourly_shortfall)
        total_curtailment = sum(energy_balance.hourly_curtailment)
        
        total_generation = sum(energy_balance.facility_totals.values())
        total_cost = sum(econ.get('annual_cost', 0) for econ in economic_results.values())
        
        # Calculate percentages
        load_met_pct = (total_load - total_shortfall) / total_load if total_load > 0 else 0
        curtailment_pct = total_curtailment / total_generation if total_generation > 0 else 0
        
        # Calculate renewable percentage
        renewable_generation = 0
        for tech_name, generation in energy_balance.facility_totals.items():
            # Assume non-storage, non-generator technologies are renewable
            if tech_name not in config['storage_names'] and tech_name not in config['generator_names']:
                renewable_generation += generation
        
        re_pct = renewable_generation / total_generation if total_generation > 0 else 0
        
        return {
            'total_load': total_load,
            'total_generation': total_generation,
            'total_shortfall': total_shortfall,
            'total_curtailment': total_curtailment,
            'total_cost': total_cost,
            'load_met_pct': load_met_pct,
            'curtailment_pct': curtailment_pct,
            'renewable_pct': re_pct,
            'system_lcoe': total_cost / (total_load - total_shortfall) if (total_load - total_shortfall) > 0 else 0,
            'energy_balance': energy_balance,
            'economic_results': economic_results
        }
    
    def _create_output_arrays(self, summary_stats, option, config) -> Tuple[np.ndarray, Optional[np.ndarray]]:
        """Create structured numpy arrays for output"""
        energy_balance = summary_stats['energy_balance']
        economic_results = summary_stats['economic_results']
        
        # Create summary array
        facilities = list(energy_balance.facility_totals.keys())
        
        summary_dtype = [
            ('facility', 'U50'),
            ('capacity', 'f8'),
            ('generation', 'f8'),
            ('cf', 'f8'),
            ('cost_per_year', 'f8'),
            ('lcoe', 'f8'),
            ('facility_type', 'U20')
        ]
        
        summary_array = np.zeros(len(facilities), dtype=summary_dtype)
        
        for i, facility_name in enumerate(facilities):
            economics = economic_results.get(facility_name, {})
            summary_array[i]['facility'] = facility_name
            summary_array[i]['generation'] = energy_balance.facility_totals[facility_name]
            summary_array[i]['cf'] = economics.get('capacity_factor', 0)
            summary_array[i]['cost_per_year'] = economics.get('annual_cost', 0)
            summary_array[i]['lcoe'] = economics.get('lcoe', 0)
        
        # Create hourly array if requested
        hourly_array = None
        if option == 'D':
            hourly_array = self._create_hourly_array(energy_balance)
        
        return summary_array, hourly_array
    
    def _create_hourly_array(self, energy_balance) -> np.ndarray:
        """Create hourly data array for detailed output"""
        num_hours = 8760
        facilities = list(energy_balance.facility_generation.keys())
        num_cols = len(facilities) + 4  # facilities + load + shortfall + surplus + curtailment
        
        hourly_array = np.zeros((num_hours, num_cols))
        
        # Fill hourly data
        for h in range(num_hours):
            col = 0
            hourly_array[h, col] = energy_balance.hourly_load[h]
            col += 1
            hourly_array[h, col] = energy_balance.hourly_shortfall[h]
            col += 1
            hourly_array[h, col] = energy_balance.hourly_surplus[h]
            col += 1
            hourly_array[h, col] = energy_balance.hourly_curtailment[h]
            col += 1
            
            for facility in facilities:
                if h < len(energy_balance.facility_generation[facility]):
                    hourly_array[h, col] = energy_balance.facility_generation[facility][h]
                col += 1
        
        return hourly_array
    
    def _compile_metadata(self, start_time, year, option, sender_name, energy_balance, 
                         summary_stats, config) -> Dict:
        """Compile comprehensive metadata"""
        return {
            'processing_time': time.time() - start_time,
            'year': year,
            'option': option,
            'sender_name': sender_name,
            'correlation_data': energy_balance.correlation_data,
            'max_lifetime': config['max_lifetime'],
            'carbon_price': self.carbon_price,
            'discount_rate': self.discount_rate,
            'total_load': summary_stats['total_load'],
            'load_met_pct': summary_stats['load_met_pct'],
            'curtailment_pct': summary_stats['curtailment_pct'],
            'renewable_pct': summary_stats['renewable_pct'],
            'system_lcoe': summary_stats['system_lcoe'],
            'storage_facilities': config['storage_names'],
            'generator_facilities': config['generator_names'],
            'underlying_facilities': config['underlying_facs']
        }
    
    def _update_progress(self, value):
        """Update progress bar if available"""
        if hasattr(self, 'listener') and self.listener and hasattr(self.listener, 'progress_bar'):
            self.listener.progress_bar.setValue(value)
        if self.event_callback:
            self.event_callback()
    
    def _update_status(self, sender_name, processing_time):
        """Update status message"""
        if processing_time < 60:
            time_str = f'{processing_time:.1f} seconds'
        else:
            time_str = f'{processing_time/60:.2f} minutes'
        
        msg = f'{sender_name} completed in {time_str}.'
        self.setStatus(msg)
        
        # Clean up progress bar
        if hasattr(self, 'listener') and self.listener and hasattr(self.listener, 'progress_bar'):
            self.listener.progress_bar.setHidden(True)
            self.listener.progress_bar.setValue(0)
