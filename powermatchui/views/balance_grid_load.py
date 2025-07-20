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
        self.area = 0.0
        for attr in ['tech_id', 'tech_name', 'tech_signature', 'tech_type', 'category', 'renewable', 'dispatchable', 'capacity', 'multiplier', 
                     'capacity_max', 'capacity_min', 'lcoe', 'lcoe_cf', 'recharge_max', 'recharge_loss', 'min_runtime', 
                     'warm_time', 'discharge_max', 'discharge_loss', 'parasitic_loss', 'emissions', 'initial','merit_order',
                     'capex', 'fixed_om', 'variable_om', 'fuel', 'lifetime', 'area']:
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
    technology_generation: Dict[str, List[float]]
    technology_totals: Dict[str, float]
    technology_to_meet_load: Dict[str, float]  # Added for LCOE calculations
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
    # Statistics tracking
    total_charge: float = 0.0
    total_discharge: float = 0.0
    total_losses: float = 0.0
    max_level_reached: float = 0.0

@dataclass
class TechnologyEconomics:
    """Complete economic metrics for a technology"""
    # Generation metrics
    capacity: float = 0.0
    generation_mwh: float = 0.0
    to_meet_load_mwh: float = 0.0
    capacity_factor: float = 0.0
    max_generation: float = 0.0
    
    # Cost metrics
    annual_cost: float = 0.0
    lcog: float = 0.0  # Levelized Cost of Generation
    lcoe: float = 0.0  # Levelized Cost of Energy (to meet load)
    capital_cost: float = 0.0
    
    # Emissions metrics
    emissions_tco2e: float = 0.0
    emissions_cost: float = 0.0
    lcoe_with_co2: float = 0.0
    
    # Lifetime metrics
    lifetime_cost: float = 0.0
    lifetime_emissions: float = 0.0
    lifetime_emissions_cost: float = 0.0
    
    # Reference metrics
    reference_lcoe: float = 0.0
    reference_cf: float = 0.0
    
    # Storage specific
    max_balance: float = 0.0  # For storage systems
    
    # Area
    area_km2: float = 0.0

class PowerMatchProcessor:
    """Enhanced PowerMatch processor with complete statistics"""
    
    def __init__(self, scenario_settings, progress_handler: Optional[ProgressHandler] = None, 
                event_callback=None, status_callback=None):
        self.listener = progress_handler
        self.event_callback = event_callback
        self.setStatus = status_callback or (lambda text: None)
        self.carbon_price = float(scenario_settings.get('carbon_price', 0.0))
        self.carbon_price_max = 200.
        self.discount_rate = float(scenario_settings.get('discount_rate', 0.0))
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
        self.adjusted_lcoe = True  # Use to meet load for LCOE calculation
        self.storage_states = []
    
    def matchSupplytoLoad(self, year, option, sender_name, technology_attributes, load_and_supply
                   ) -> DispatchResults:
        """
        Main dispatch function with complete statistics calculation
        """
        start_time = time.time()
        
        # Initialize processing
        config = self._initialize_dispatch(year, option, technology_attributes)
        
        # Calculate energy balance with proper merit order dispatch
        energy_balance = self._calculate_energy_balance(technology_attributes, load_and_supply, config)
        
        # Calculate comprehensive economic metrics
        economic_results = self._calculate_comprehensive_economics(
            energy_balance, technology_attributes, config
        )
        
        # Generate summary statistics
        summary_stats = self._generate_summary_statistics(
            energy_balance, economic_results, technology_attributes, config
        )
        
        # Create output arrays
        summary_array, hourly_array = self._create_output_arrays(
            summary_stats, economic_results, option, config
        )
        
        # Compile metadata
        metadata = self._compile_metadata(
            start_time, year, energy_balance, 
            summary_stats, economic_results, config
        )
        
        self._update_status(sender_name, time.time() - start_time)
        
        return DispatchResults(summary_array, hourly_array, metadata)
    
    def _initialize_dispatch(self, year, option, technology_attributes) -> Dict:
        """Initialize dispatch configuration and parameters"""
        config = {
            'year': year,
            'option': option,
            'the_days': [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31],
            'sf_test': ['<', '>'] if self.surplus_sign >= 0 else ['>', '<'],
            'sf_sign': ['-', '+'] if self.surplus_sign >= 0 else ['+', '-'],
            'max_lifetime': self._calculate_max_lifetime(technology_attributes),
            'underlying_facs': self._identify_underlying_technologies(technology_attributes),
            'storage_names': [],
            'generator_names': [],
            'renewable_names': [],
        }
        
        # Identify technology types
        for tech_name, details in technology_attributes.items():
            if tech_name == 'Load':
                continue
            if details.tech_type == 'S':  # Storage
                config['storage_names'].append(tech_name)
            elif details.tech_type == 'G':  # Generator
                config['generator_names'].append(tech_name)
            if details.renewable:
                if tech_name not in config['renewable_names']:
                    config['renewable_names'].append(tech_name)
        
        self._update_progress(6)
        return config
    
    def _calculate_max_lifetime(self, technology_attributes) -> float:
        """Calculate maximum lifetime across all technologies"""
        max_lifetime = 0
        for key, details in technology_attributes.items():
            if key in ['Load', 'Total']:
                continue
            if details.capacity * details.multiplier > 0:
                max_lifetime = max(max_lifetime, details.lifetime)
        return max_lifetime
    
    def _identify_underlying_technologies(self, technology_attributes) -> List[str]:
        """Identify technologies that contribute to underlying load"""
        underlying_facs = []
        for tech_name, details in technology_attributes.items():
            if tech_name == 'Load':
                continue
            if tech_name in self.operational:
                continue
            
            base_name = tech_name.split('.')[-1] if '.' in tech_name else tech_name
            if tech_name in self.underlying or base_name in self.underlying:
                underlying_facs.append(tech_name)
        
        return underlying_facs
    
    def _calculate_energy_balance(self, technology_attributes, load_and_supply, config) -> EnergyBalance:
        """
        Calculate hourly energy balance with proper merit order dispatch including storage
        """
        # Initialize tracking arrays
        hourly_load = []
        hourly_shortfall = []
        hourly_surplus = []
        hourly_curtailment = []
        technology_generation = {}
        technology_totals = {}
        technology_to_meet_load = {}
        
        # Get load data
        load_col = technology_attributes['Load'].merit_order
        load_multiplier = technology_attributes['Load'].multiplier
        
        # Initialize storage states and store as instance variable
        self.storage_states = self._initialize_storage_states(technology_attributes)
        
        # Initialize facility tracking
        for tech_name in technology_attributes.keys():
            if tech_name != 'Load':
                technology_generation[tech_name] = []
                technology_totals[tech_name] = 0.0
                technology_to_meet_load[tech_name] = 0.0
        
        # Process each hour
        for h in range(8760):
            # Get hourly load
            load_h = load_and_supply[load_col][h] * load_multiplier
            hourly_load.append(load_h)
            
            # Start with load as the remaining demand to meet
            remaining_demand = load_h
            hour_curtailment = 0.0
            
            # Track what each technology contributes to meeting load
            hour_to_meet_load = {}
            for tech_name in technology_attributes.keys():
                if tech_name != 'Load':
                    hour_to_meet_load[tech_name] = 0.0
            
            # Apply parasitic losses to storage first
            for storage_state in self.storage_states:
                if storage_state.current_level > 0:
                    parasitic_loss = storage_state.current_level * storage_state.parasitic_loss / 24
                    storage_state.current_level = max(0, storage_state.current_level - parasitic_loss)
                    storage_state.total_losses += parasitic_loss
            
            # Process technologies in merit order
            for tech_name, details in technology_attributes.items():
                if tech_name == 'Load':
                    continue
                # For dispatchable technologies use the nameplate capacity otherwise the the SAM derived capacity
                if details.dispatchable:
                    capacity = details.capacity * details.multiplier
                else:
                    capacity = load_and_supply[details.merit_order][h] * details.multiplier
                if capacity == 0:
                    technology_generation[tech_name].append(0)
                    continue
                
                hour_generation = 0.0
                
                if details.tech_type == 'S':  # Storage
                    hour_generation = self._dispatch_storage_hour(
                        tech_name, self.storage_states, remaining_demand, h
                    )
                    hour_to_meet_load[tech_name] = hour_generation
                    remaining_demand = max(0, remaining_demand - hour_generation)
                
                elif details.tech_type == 'G':  # Generator
                    if details.dispatchable:
                        hour_generation = self._dispatch_generator_hour(
                            tech_name, details, remaining_demand, h
                        )
                        hour_to_meet_load[tech_name] = hour_generation
                        remaining_demand = max(0, remaining_demand - hour_generation)
                
                    else:  # Non-dispatchable renewable
                        available_generation = self._get_renewable_generation(
                            tech_name, details, load_and_supply, h
                        )
                        
                        if remaining_demand > 0:
                            # Use what's needed to meet demand
                            hour_generation = min(available_generation, remaining_demand)
                            hour_to_meet_load[tech_name] = hour_generation
                            remaining_demand -= hour_generation
                            
                            # Curtail excess renewable
                            curtailed = available_generation - hour_generation
                            hour_curtailment += curtailed
                        else:
                            # All renewable is curtailed if no demand
                            hour_curtailment += available_generation
                            hour_generation = 0
                            hour_to_meet_load[tech_name] = 0
                    
                # Track generation
                technology_generation[tech_name].append(hour_generation)
                technology_totals[tech_name] += hour_generation
                technology_to_meet_load[tech_name] += hour_to_meet_load[tech_name]
            
            # Handle any excess capacity for storage charging
            if hour_curtailment > 0:
                charged_energy = self._charge_storage_systems(self.storage_states, hour_curtailment)
                hour_curtailment -= charged_energy
            
            # Record hourly results
            hourly_shortfall.append(remaining_demand)
            hourly_surplus.append(0 if remaining_demand > 0 else abs(remaining_demand))
            hourly_curtailment.append(hour_curtailment)
        
        # Update storage statistics
        for storage_state in self.storage_states:
            if storage_state.max_level_reached < storage_state.capacity:
                # Cpture the final level as a potential maximum
                storage_state.max_level_reached = max(
                    storage_state.max_level_reached,
                    storage_state.current_level
                )
        
        # Calculate correlation if requested
        correlation_data = None
        if self.show_correlation:
            correlation_data = self._calculate_correlation(
                hourly_load, technology_generation, load_and_supply, load_col
            )
        
        return EnergyBalance(
            hourly_load=hourly_load,
            hourly_shortfall=hourly_shortfall,
            hourly_surplus=hourly_surplus,
            hourly_curtailment=hourly_curtailment,
            technology_generation=technology_generation,
            technology_totals=technology_totals,
            technology_to_meet_load=technology_to_meet_load,
            correlation_data=correlation_data
        )
    
    def _initialize_storage_states(self, technology_attributes) -> List[StorageState]:
        """Initialize storage system states"""
        storage_states = []
        
        for tech_name, details in technology_attributes.items():
            if details.tech_type == 'S':  # Storage
                capacity = details.capacity * details.multiplier
                if capacity > 0:
                    storage_state = StorageState(
                        name=tech_name,
                        capacity=capacity,
                        current_level=details.initial * details.multiplier,
                        min_level=capacity * details.capacity_min,
                        max_level=capacity * details.capacity_max if details.capacity_max > 0 else capacity,
                        charge_rate=capacity * details.recharge_max if details.recharge_max > 0 else capacity,
                        discharge_rate=capacity * details.discharge_max if details.discharge_max > 0 else capacity,
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
    
    def _get_renewable_generation(self, tech_name, details, load_and_supply, hour) -> float:
        """Get available renewable generation for this hour"""
        merit_order = details.merit_order
        if merit_order > 0 and merit_order < len(load_and_supply) and hour < len(load_and_supply[merit_order]):
            return load_and_supply[merit_order][hour] * details.multiplier
        else:
            # Constant generation facility or missing data
            return details.capacity * details.multiplier
    
    def _dispatch_storage_hour(self, tech_name, storage_states, remaining_demand, hour) -> float:
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
            storage_state.total_discharge += energy_delivered
            storage_state.total_losses += max_discharge - energy_delivered
            
            # Update max level reached
            storage_state.max_level_reached = max(
                storage_state.max_level_reached, storage_state.current_level
            )
            
            # Update operating state
            storage_state.hours_in_discharge += 1
            
            return energy_delivered
        
        return 0.0
    
    def _should_start_discharge_run(self, storage_state, current_hour, current_demand) -> bool:
        """Check if storage should start a discharge run based on minimum runtime"""
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
                storage_state.total_charge += max_charge
                storage_state.total_losses += max_charge - energy_stored
                
                # Update max level reached
                storage_state.max_level_reached = max(
                    storage_state.max_level_reached, storage_state.current_level
                )
                
                # Reduce available energy
                available_energy -= max_charge
                charged_total += max_charge
                
                # Reset discharge run state
                storage_state.discharge_run_active = False
                storage_state.warm_run_active = False
                storage_state.hours_in_discharge = 0
        
        return charged_total
    
    def _calculate_correlation(self, hourly_load, technology_generation, load_and_supply, load_col) -> List:
        """Calculate correlation between load and renewable generation"""
        try:
            # Calculate total renewable contribution
            total_renewable = []
            for h in range(len(hourly_load)):
                hour_renewable = 0
                for tech_name, generation_profile in technology_generation.items():
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
    
    def _calculate_comprehensive_economics(self, energy_balance, technology_attributes, config) -> Dict[str, TechnologyEconomics]:
        """Calculate comprehensive economic metrics for all technologies"""
        economic_results = {}
        
        # Calculate total renewable generation for storage LCOE allocation
        total_renewable_tml = 0.0
        storage_contribution = 0.0
        
        for tech_name in config['renewable_names']:
            if tech_name in energy_balance.technology_to_meet_load:
                total_renewable_tml += energy_balance.technology_to_meet_load[tech_name]
        
        for tech_name in config['storage_names']:
            if tech_name in energy_balance.technology_to_meet_load:
                storage_contribution += energy_balance.technology_to_meet_load[tech_name]
        
        # Calculate economics for each technology
        for tech_name, details in technology_attributes.items():
            if tech_name == 'Load':
                continue
                
            capacity = details.capacity * details.multiplier
            if capacity > 0:
                economics = self._calculate_technology_comprehensive_economics(
                    tech_name, details, capacity, energy_balance, config,
                    total_renewable_tml, storage_contribution
                )
                economic_results[tech_name] = economics
        
        return economic_results
    
    def _find_storage_state(self, tech_name: str) -> Optional[StorageState]:
        """Find storage state for a given technology name"""
        for storage_state in self.storage_states:
            if storage_state.name == tech_name:
                return storage_state
        return None
    
    def _calculate_technology_comprehensive_economics(self, tech_name, details, capacity, 
                                                    energy_balance, config, total_renewable_tml, 
                                                    storage_contribution) -> TechnologyEconomics:
        """Calculate comprehensive economic metrics for a single technology"""
        economics = TechnologyEconomics()
        
        # Basic generation metrics
        economics.capacity = capacity
        economics.generation_mwh = energy_balance.technology_totals.get(tech_name, 0)
        economics.to_meet_load_mwh = energy_balance.technology_to_meet_load.get(tech_name, 0)
        economics.capacity_factor = economics.generation_mwh / (capacity * 8760) if capacity > 0 else 0
        
        # Max generation
        if tech_name in energy_balance.technology_generation:
            economics.max_generation = max(energy_balance.technology_generation[tech_name])
        
        # Calculate costs based on cost structure
        if (details.capex > 0 or details.fixed_om > 0 or 
            details.variable_om > 0 or details.fuel > 0):
            
            # Full cost calculation
            economics.capital_cost = capacity * details.capex
            opex = (capacity * details.fixed_om + 
                   economics.generation_mwh * details.variable_om + 
                   economics.generation_mwh * details.fuel)
            
            economics.lcog = self._calc_lcoe(economics.generation_mwh, economics.capital_cost, 
                                           opex, self.discount_rate, details.lifetime)
            economics.annual_cost = economics.generation_mwh * economics.lcog
            
        elif details.lcoe > 0:
            # Reference LCOE calculation
            cf = details.lcoe_cf if details.lcoe_cf > 0 else economics.capacity_factor
            economics.annual_cost = details.lcoe * cf * 8760 * capacity
            economics.lcog = details.lcoe if economics.generation_mwh > 0 else 0
            economics.reference_lcoe = details.lcoe
            economics.reference_cf = cf
            
        elif details.lcoe_cf == 0:  # No cost facility
            economics.annual_cost = 0
            economics.lcog = 0
            economics.reference_lcoe = details.lcoe
            economics.reference_cf = economics.capacity_factor
        
        # Calculate LCOE (cost per MWh to meet load)
        if economics.to_meet_load_mwh > 0:
            if tech_name in config['renewable_names'] and total_renewable_tml > 0 and storage_contribution > 0:
                # For renewables with storage, allocate storage contribution
                storage_allocation = (storage_contribution * economics.to_meet_load_mwh / total_renewable_tml)
                total_load_served = economics.to_meet_load_mwh + storage_allocation
                economics.lcoe = economics.annual_cost / total_load_served
            else:
                economics.lcoe = economics.annual_cost / economics.to_meet_load_mwh
        else:
            economics.lcoe = economics.lcog
        
        # Emissions calculations
        if details.emissions > 0:
            economics.emissions_tco2e = economics.generation_mwh * details.emissions
            economics.emissions_cost = economics.emissions_tco2e * self.carbon_price
            
            # LCOE with CO2
            if economics.to_meet_load_mwh > 0:
                economics.lcoe_with_co2 = (economics.annual_cost + economics.emissions_cost) / economics.to_meet_load_mwh
            else:
                economics.lcoe_with_co2 = economics.lcoe
        else:
            economics.lcoe_with_co2 = economics.lcoe
        
        # Lifetime calculations
        economics.lifetime_cost = economics.annual_cost * config['max_lifetime']
        economics.lifetime_emissions = economics.emissions_tco2e * config['max_lifetime']
        economics.lifetime_emissions_cost = economics.emissions_cost * config['max_lifetime']
        
        # Storage specific metrics
        if details.tech_type == 'S':
            # Find storage state for max balance using the implemented function
            storage_state = self._find_storage_state(tech_name)
            if storage_state:
                economics.max_balance = storage_state.max_level_reached
        
        # Area calculation
        if details.area > 0:
            economics.area_km2 = capacity * details.area
        
        return economics
    def _calc_lcoe(self, annual_output, capital_cost, annual_operating_cost, discount_rate, lifetime):
        """Calculate levelized cost of electricity"""
        if discount_rate > 0:
            annual_cost_capital = capital_cost * discount_rate * pow(1 + discount_rate, lifetime) / \
                                  (pow(1 + discount_rate, lifetime) - 1)
        else:
            annual_cost_capital = capital_cost / lifetime
        
        total_annual_cost = annual_cost_capital + annual_operating_cost
        
        try:
            return total_annual_cost / annual_output if annual_output > 0 else total_annual_cost
        except ZeroDivisionError:
            return total_annual_cost
    
    def _generate_summary_statistics(self, energy_balance, economic_results, technology_attributes, config) -> Dict:
        """Generate comprehensive summary statistics"""
        # Calculate totals
        total_load = sum(energy_balance.hourly_load)
        total_shortfall = sum(energy_balance.hourly_shortfall)
        total_curtailment = sum(energy_balance.hourly_curtailment)
        
        total_generation = sum(energy_balance.technology_totals.values())
        total_cost = sum(econ.annual_cost for econ in economic_results.values())
        total_emissions = sum(econ.emissions_tco2e for econ in economic_results.values())
        total_emissions_cost = sum(econ.emissions_cost for econ in economic_results.values())
        total_capital_cost = sum(econ.capital_cost for econ in economic_results.values())
        total_area = sum(econ.area_km2 for econ in economic_results.values())
        
        # Calculate percentages
        load_met_pct = (total_load - total_shortfall) / total_load if total_load > 0 else 0
        curtailment_pct = total_curtailment / total_generation if total_generation > 0 else 0
        
        # Calculate renewable percentage
        renewable_generation = 0
        renewable_to_meet_load = 0
        storage_generation = 0
        fossil_generation = 0
        
        for tech_name, generation in energy_balance.technology_totals.items():
            details = technology_attributes.get(tech_name, None)
            if details.renewable:
                renewable_generation += generation
                renewable_to_meet_load += energy_balance.technology_to_meet_load.get(tech_name, 0)
            if details.tech_type == 'S':  # Storage
                storage_generation += energy_balance.technology_to_meet_load.get(tech_name, 0)
            elif details.tech_type == 'G' and not details.renewable and details.fuel > 0:  # Generator
                fossil_generation += generation
        
        re_pct = renewable_generation / total_generation if total_generation > 0 else 0
        re_load_pct = (renewable_to_meet_load + storage_generation) / total_load if total_load > 0 else 0
        storage_pct = storage_generation / total_load if total_load > 0 else 0
        
        return {
            'total_load': total_load,
            'total_generation': total_generation,
            'total_shortfall': total_shortfall,
            'total_curtailment': total_curtailment,
            'total_cost': total_cost,
            'total_emissions': total_emissions,
            'total_emissions_cost': total_emissions_cost,
            'total_capital_cost': total_capital_cost,
            'total_area': total_area,
            'load_met_pct': load_met_pct,
            'curtailment_pct': curtailment_pct,
            'renewable_pct': re_pct,
            'renewable_load_pct': re_load_pct,
            'storage_pct': storage_pct,
            'system_lcoe': total_cost / (total_load - total_shortfall) if (total_load - total_shortfall) > 0 else 0,
            'system_lcoe_with_co2': (total_cost + total_emissions_cost) / (total_load - total_shortfall) if (total_load - total_shortfall) > 0 else 0,
            'energy_balance': energy_balance,
            'economic_results': economic_results
        }
    
    def _create_output_arrays(self, summary_stats, economic_results, option, config) -> Tuple[np.ndarray, Optional[np.ndarray]]:
        """Create structured numpy arrays for output with complete statistics"""
        energy_balance = summary_stats['energy_balance']
        
        # Create comprehensive summary array
        technologies = list(energy_balance.technology_totals.keys())
        
        summary_dtype = [
            ('technology', 'U50'),
            ('capacity_mw', 'f8'),
            ('generation_mwh', 'f8'),
            ('to_meet_load_mwh', 'f8'),
            ('capacity_factor', 'f8'),
            ('annual_cost', 'f8'),
            ('lcog_per_mwh', 'f8'),
            ('lcoe_per_mwh', 'f8'),
            ('emissions_tco2e', 'f8'),
            ('emissions_cost', 'f8'),
            ('lcoe_with_co2_per_mwh', 'f8'),
            ('max_generation_mw', 'f8'),
            ('max_balance', 'f8'),  # For storage
            ('capital_cost', 'f8'),
            ('lifetime_cost', 'f8'),
            ('lifetime_emissions', 'f8'),
            ('lifetime_emissions_cost', 'f8'),
            ('area_km2', 'f8'),
            ('reference_lcoe', 'f8'),
            ('reference_cf', 'f8'),
        ]
        
        summary_array = np.zeros(len(technologies), dtype=summary_dtype)
        
        for i, tech_name in enumerate(technologies):
            economics = economic_results.get(tech_name, TechnologyEconomics())
            
            summary_array[i]['technology'] = tech_name
            summary_array[i]['capacity_mw'] = economics.capacity
            summary_array[i]['generation_mwh'] = economics.generation_mwh
            summary_array[i]['to_meet_load_mwh'] = economics.to_meet_load_mwh
            summary_array[i]['capacity_factor'] = economics.capacity_factor
            summary_array[i]['annual_cost'] = economics.annual_cost
            summary_array[i]['lcog_per_mwh'] = economics.lcog
            summary_array[i]['lcoe_per_mwh'] = economics.lcoe
            summary_array[i]['emissions_tco2e'] = economics.emissions_tco2e
            summary_array[i]['emissions_cost'] = economics.emissions_cost
            summary_array[i]['lcoe_with_co2_per_mwh'] = economics.lcoe_with_co2
            summary_array[i]['max_generation_mw'] = economics.max_generation
            summary_array[i]['max_balance'] = economics.max_balance
            summary_array[i]['capital_cost'] = economics.capital_cost
            summary_array[i]['lifetime_cost'] = economics.lifetime_cost
            summary_array[i]['lifetime_emissions'] = economics.lifetime_emissions
            summary_array[i]['lifetime_emissions_cost'] = economics.lifetime_emissions_cost
            summary_array[i]['area_km2'] = economics.area_km2
            summary_array[i]['reference_lcoe'] = economics.reference_lcoe
            summary_array[i]['reference_cf'] = economics.reference_cf
        
        # Create hourly array if requested
        hourly_array = None
        if option == 'D':
            hourly_array = self._create_hourly_array(energy_balance)
        
        return summary_array, hourly_array
    
    def _create_hourly_array(self, energy_balance) -> np.ndarray:
        """Create hourly data array for detailed output"""
        num_hours = 8760
        technologies = list(energy_balance.technology_generation.keys())
        num_cols = len(technologies) + 4  # technologies + load + shortfall + surplus + curtailment
        
        hourly_dtype = [
            ('hour', 'i4'),
            ('load_mw', 'f8'),
            ('shortfall_mw', 'f8'),
            ('surplus_mw', 'f8'),
            ('curtailment_mw', 'f8')
        ]
        
        # Add technology columns
        for tech in technologies:
            hourly_dtype.append((f'{tech}_mw', 'f8'))
        
        hourly_array = np.zeros(num_hours, dtype=hourly_dtype)
        
        # Fill hourly data
        for h in range(num_hours):
            hourly_array[h]['hour'] = h + 1
            hourly_array[h]['load_mw'] = energy_balance.hourly_load[h]
            hourly_array[h]['shortfall_mw'] = energy_balance.hourly_shortfall[h]
            hourly_array[h]['surplus_mw'] = energy_balance.hourly_surplus[h]
            hourly_array[h]['curtailment_mw'] = energy_balance.hourly_curtailment[h]
            
            for tech in technologies:
                if h < len(energy_balance.technology_generation[tech]):
                    hourly_array[h][f'{tech}_mw'] = energy_balance.technology_generation[tech][h]
        
        return hourly_array
    
    def _compile_metadata(self, start_time, year, energy_balance, 
                         summary_stats, economic_results, config) -> Dict:
        """Compile comprehensive metadata"""
        # Find max shortfall and when it occurred
        max_shortfall = 0
        max_shortfall_hour = 0
        for h, shortfall in enumerate(energy_balance.hourly_shortfall):
            if shortfall > max_shortfall:
                max_shortfall = shortfall
                max_shortfall_hour = h
        
        # Calculate system totals
        system_totals = {
            'total_capacity_mw': sum(econ.capacity for econ in economic_results.values()),
            'total_generation_mwh': sum(econ.generation_mwh for econ in economic_results.values()),
            'total_to_meet_load_mwh': sum(econ.to_meet_load_mwh for econ in economic_results.values()),
            'total_annual_cost': summary_stats['total_cost'],
            'total_emissions_tco2e': summary_stats['total_emissions'],
            'total_emissions_cost': summary_stats['total_emissions_cost'],
            'total_capital_cost': summary_stats['total_capital_cost'],
            'total_lifetime_cost': sum(econ.lifetime_cost for econ in economic_results.values()),
            'total_lifetime_emissions': sum(econ.lifetime_emissions for econ in economic_results.values()),
            'total_lifetime_emissions_cost': sum(econ.lifetime_emissions_cost for econ in economic_results.values()),
            'total_area_km2': summary_stats['total_area']
        }
        
        return {
            'processing_time': time.time() - start_time,
            'year': year,
            'correlation_data': energy_balance.correlation_data,
            'max_lifetime': config['max_lifetime'],
            'carbon_price': self.carbon_price,
            'discount_rate': self.discount_rate,
            
            # Load and system performance
            'total_load_mwh': summary_stats['total_load'],
            'load_met_pct': summary_stats['load_met_pct'],
            'total_shortfall_mwh': summary_stats['total_shortfall'],
            'max_shortfall_mw': max_shortfall,
            'max_shortfall_hour': max_shortfall_hour + 1,  # 1-indexed for display
            'total_curtailment_mwh': summary_stats['total_curtailment'],
            'curtailment_pct': summary_stats['curtailment_pct'],
            
            # Renewable energy metrics
            'renewable_pct': summary_stats['renewable_pct'],
            'renewable_load_pct': summary_stats['renewable_load_pct'],
            'storage_pct': summary_stats['storage_pct'],
            
            # Economic metrics
            'system_lcoe': summary_stats['system_lcoe'],
            'system_lcoe_with_co2': summary_stats['system_lcoe_with_co2'],
            
            # Technology categories
            'storage_technologies': config['storage_names'],
            'generator_technologies': config['generator_names'],
            'renewable_technologies': config['renewable_names'],
            'underlying_technologies': config['underlying_facs'],
            
            # System totals
            'system_totals': system_totals,
            
            # Configuration
            'adjusted_lcoe': self.adjusted_lcoe,
            'remove_cost': self.remove_cost,
            'surplus_sign': self.surplus_sign
        }
    
    def _update_progress(self, value, message=None):
        """Update progress bar if available"""
        if hasattr(self, 'listener') and self.listener:
            if hasattr(self.listener, 'progress_bar'):
                self.listener.progress_bar.setValue(value)
            if hasattr(self.listener, 'update') and message:
                self.listener.update(step=value, message=message, increment=False)
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

# Helper functions for creating summary reports and Excel output

def export_to_excel(dispatch_results: DispatchResults, filename: str):
    """Export dispatch results to Excel format"""
    try:
        import pandas as pd
        
        summary_df = pd.DataFrame(dispatch_results.summary_data)
        
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            # Summary sheet
            summary_df.to_excel(writer, sheet_name='Summary', index=False)
            
            # Hourly data sheet (if available)
            if dispatch_results.hourly_data is not None:
                hourly_df = pd.DataFrame(dispatch_results.hourly_data)
                hourly_df.to_excel(writer, sheet_name='Hourly_Data', index=False)
            
            # Metadata sheet
            metadata_df = pd.DataFrame([dispatch_results.metadata])
            metadata_df.to_excel(writer, sheet_name='Metadata', index=False)
        
        return f"Results exported to {filename}"
        
    except ImportError:
        return "pandas not available for Excel export"
    except Exception as e:
        return f"Export failed: {str(e)}"
