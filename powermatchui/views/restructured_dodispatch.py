# doDispatch() → 
#   ├── _initialize_dispatch()
#   ├── _calculate_energy_balance()
#   ├── _process_renewables()
#   ├── _process_dispatch_order()
#   │   ├── _process_storage()
#   │   └── _process_generator()
#   ├── _calculate_economics()
#   ├── _generate_summary_statistics()
#   ├── _create_output_arrays()
#   └── _compile_metadata()

import numpy as np
import time
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from powermatchui.views.progress_handler import ProgressHandler

@dataclass
class Technology:
    def __init__(self, **kwargs):
        kwargs = {**kwargs}
      #  return
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
    shortfall: List[float]
    facility_contributions: Dict[str, float]
    load_data: List[float]
    correlation_data: Optional[List]

@dataclass
class StorageState:
    """Container for storage system state"""
    capacity: float
    initial_level: float
    min_level: float
    max_level: float
    charge_rate: float
    discharge_rate: float
    charge_efficiency: float
    discharge_efficiency: float
    parasitic_loss: float

class PowerMatchProcessor:
    """Restructured PowerMatch processor with modular dispatch functions"""
    def __init__(self, config, scenarios, progress_handler: Optional[ProgressHandler] = None, 
                event_callback=None, status_callback=None):
        self.config = config  # Access configuration details
        self.scenarios = scenarios
        self.listener = progress_handler
        self.event_callback = event_callback  # UI passes its event-processing function
        self.setStatus = status_callback or (lambda text: None)  # Default to no-op
        self.adjusted_lcoe = True
        self.carbon_price = 0.
        self.carbon_price_max = 200.
        self.discount_rate = 0.
        self.load_folder = ''
        self.load_year = 'n/a'
        self.optimise_choice = 'LCOE'
        self.optimise_generations = 20
        self.optimise_mutation = 0.005
        self.optimise_population = 50
        self.optimise_stop = 0
        self.optimise_debug = False
        self.optimise_default = None
        self.optimise_multiplot = True
        self.optimise_multisurf = False
        self.optimise_multitable = False
        self.optimise_to_batch = True
        self.remove_cost = True
        self.results_prefix = ''
        self.surplus_sign = 1 # Note: Preferences file has it called shortfall_sign
        # it's easier for the user to understand while for the program logic surplus is easier
        self.underlying = ['Rooftop PV'] # technologies contributing to underlying (but not operational) load
        self.operational = []
        self.show_correlation = False
    
    def doDispatch(self, year, option, sender_name, pmss_details, pmss_data
                   ) -> DispatchResults:
        """
        Main dispatch function - now acts as a coordinator calling specialized methods
        """
        start_time = time.time()
        
        # Initialize processing
        config = self._initialize_dispatch(year, option, pmss_details)
        
        # Calculate energy balance
        energy_balance = self._calculate_energy_balance(pmss_details, pmss_data)
        
        # Process renewable facilities
        renewable_results = self._process_renewables(pmss_details, pmss_data, energy_balance)
        
        # Process storage and generators
        dispatch_results = self._process_dispatch_order(
            pmss_details, energy_balance, option, config
        )
        
        # Calculate economic metrics
        economic_results = self._calculate_economics(
            renewable_results, dispatch_results, pmss_details
        )
        
        # Generate summary statistics
        summary_stats = self._generate_summary_statistics(
            renewable_results, dispatch_results, economic_results, energy_balance, config
        )
        
        # Create output arrays
        summary_array, hourly_array = self._create_output_arrays(
            summary_stats, dispatch_results, option, config
        )
        
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
        }
        
        # Update progress if UI is available
        self._update_progress(6)
        
        return config
    
    def _calculate_max_lifetime(self, pmss_details) -> float:
        """Calculate maximum lifetime across all technologies"""
        max_lifetime = 0
        for key, details in pmss_details.items():
            if key in ['Load', 'Total']:
                continue
            if details.capacity * details.multiplier > 0:
                gen = details.tech_name
                if gen in pmss_details:
                    max_lifetime = max(max_lifetime, pmss_details[gen].lifetime)
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
        """Calculate hourly energy balance and facility contributions"""
        load_col = pmss_details['Load'].merit_order
        load_multiplier = pmss_details['Load'].multiplier
        
        # Get technologies sorted by merit order (excluding Load)
        tech_order = sorted(
            [tech for tech in pmss_details.keys() if tech != 'Load'],
            key=lambda tech: pmss_details[tech].merit_order
        )
        
        # Initialize arrays
        shortfall = [0.0] * 8760
        tech_contributions = {}
        load_data = []
        
        # Calculate hourly load and shortfall
        for h in range(8760):
            load_h = pmss_data[load_col][h] * load_multiplier
            load_data.append(load_h)
            shortfall[h] = load_h
            
            # Subtract renewable generation
            for tech in tech_order:
                if tech not in tech_contributions:
                    tech_contributions[tech] = 0.0
                
                if pmss_details[tech].merit_order > 0:
                    if pmss_details[tech].merit_order in pmss_data:
                        generation = pmss_data[pmss_details[tech].merit_order][h] * pmss_details[tech].multiplier
                    else:
                        generation = pmss_details[tech].capacity * pmss_details[tech].multiplier
                    shortfall[h] -= generation
            
            # Calculate allocation factor for curtailment
            if shortfall[h] >= 0:
                alloc = 1.0
            else:
                alloc = load_h / (load_h - shortfall[h])
            
            # Update facility contributions with curtailment
            for tech in tech_order:
                if pmss_details[tech].merit_order > 0:
                    if pmss_details[tech].merit_order in pmss_data:
                        generation = pmss_data[pmss_details[tech].merit_order][h] * pmss_details[tech].multiplier
                    else:
                        generation = pmss_details[tech].capacity * pmss_details[tech].multiplier
                    tech_contributions[tech] += generation * alloc
        
        # Calculate correlation if requested
        correlation_data = None
        if self.show_correlation:
            correlation_data = self._calculate_correlation(load_data, shortfall, pmss_data, load_col)
        
        return EnergyBalance(shortfall, tech_contributions, load_data, correlation_data)    

    def _calculate_correlation(self, load_data, shortfall, pmss_data, load_col) -> List:
        """Calculate correlation between load and renewable generation"""
        # Prepare data for correlation
        if pmss_details['Load'].multiplier == 1:
            df1 = pmss_data[load_col]
        else:
            df1 = [pmss_data[load_col][h] * pmss_details['Load'].multiplier for h in range(8760)]
        
        corr_src = []
        for h in range(len(shortfall)):
            if shortfall[h] < 0:
                corr_src.append(pmss_data[load_col][h])
            else:
                corr_src.append(pmss_data[load_col][h] - shortfall[h])
        
        try:
            corr = np.corrcoef(df1, corr_src)
            if np.isnan(corr.item((0, 1))):
                corr = 0
            else:
                corr = corr.item((0, 1))
        except:
            corr = 0
        
        return [['Correlation To Load'], ['RE Contribution', corr]]
    
    def _process_renewables(self, pmss_details, pmss_data, energy_balance) -> List[Dict]:
        """Process renewable energy facilities"""
        renewable_results = []
        
        # Get technologies sorted by merit order (excluding Load)
        tech_order = sorted(
            [tech for tech in pmss_details.keys() if tech != 'Load'],
            key=lambda tech: pmss_details[tech].merit_order
        )
        
        for tech in tech_order:
            if tech in energy_balance.facility_contributions:
                result = self._process_single_renewable(tech, pmss_details, pmss_data, energy_balance)
                if result:
                    renewable_results.append(result)
        
        return renewable_results
    
    def _process_single_renewable(self, tech_name, pmss_details, pmss_data, energy_balance) -> Optional[Dict]:
        """Process a single renewable facility using energy_balance data"""
        details = pmss_details[tech_name]
        if details.capacity * details.multiplier == 0:
            return None
        
        merit_order = details.merit_order
        if merit_order <= 0:
            return None
        
        # Calculate facility metrics using energy_balance
        capacity = details.capacity * details.multiplier
        
        # Get contribution to load from energy_balance (accounts for curtailment)
        to_meet_load = energy_balance.facility_contributions.get(tech_name, 0)
        
        # Calculate total generation and max generation from pmss_data if available
        if merit_order in pmss_data:
            # Raw generation profile before curtailment
            raw_generation_profile = [pmss_data[merit_order][h] * details.multiplier for h in range(8760)]
            total_generation = sum(raw_generation_profile)
            max_generation = max(raw_generation_profile)
        else:
            # For constant generation facilities
            total_generation = capacity * 8760  # Assumes constant output
            max_generation = capacity
        
        # Calculate capacity factor based on raw generation
        capacity_factor = total_generation / (capacity * 8760) if capacity > 0 else 0
        
        # Calculate curtailment
        curtailed_energy = total_generation - to_meet_load
        curtailment_pct = curtailed_energy / total_generation if total_generation > 0 else 0
        
        return {
            'facility': tech_name,
            'capacity': capacity,
            'capex': details.capex,
            'fixed_om': details.fixed_om,
            'variable_om': details.variable_om, 
            'fuel': details.fuel, 
            'disc_rate': details.disc_rate, 
            'lifetime': details.lifetime,
            'to_meet_load': to_meet_load,  # Energy actually used (after curtailment)
            'subtotal': total_generation,  # Total energy generated (before curtailment)
            'max_mwh': max_generation,
            'cf': capacity_factor,  # Based on raw generation
            'curtailed_energy': curtailed_energy,
            'curtailment_pct': curtailment_pct,
            'facility_type': 'renewable'
        }

    def _process_dispatch_order(self, pmss_details, energy_balance, option, config) -> List[Dict]:
        """Process generators and storage in dispatch order"""
        dispatch_results = []
        
        # Get generators and storage sorted by merit order (excluding Load and renewables)
        # Assuming generators/storage have different categories or can be identified
        dispatch_order = sorted(
            [tech for tech in pmss_details.keys() if tech != 'Load' and 
            pmss_details[tech].category in ['Generator', 'Storage']],  # Adjust categories as needed
            key=lambda tech: pmss_details[tech].merit_order
        )
        
        short_taken = self._handle_minimum_generation(pmss_details, energy_balance)
        
        for gen_name in dispatch_order:
            generator = pmss_details[gen_name]
            
            if generator.category == 'Storage':
                result = self._process_storage(gen_name, pmss_details, energy_balance, option, config)
            else:
                result = self._process_generator(gen_name, pmss_details, energy_balance, short_taken, config)
            
            if result:
                dispatch_results.append(result)
        
        return dispatch_results
    
    def _handle_minimum_generation(self, pmss_details, energy_balance) -> Dict[str, float]:
        """Handle minimum generation requirements for generators"""
        short_taken = {}
        short_taken_tot = 0
        
        # Get generators sorted by merit order
        generators_order = sorted(
            [tech for tech in pmss_details.keys() if 
            pmss_details[tech].tech_type == 'G'],
            key=lambda tech: pmss_details[tech].merit_order
        )
        
        for gen_name in generators_order:
            try:                
                if pmss_details[gen_name].capacity_min != 0:
                    capacity = pmss_details[gen_name].capacity * pmss_details[gen_name].multiplier
                    min_gen = capacity * pmss_details[gen_name].capacity_min
                    short_taken[gen_name] = min_gen
                    short_taken_tot += min_gen
                    
                    # Reduce shortfall by minimum generation
                    for h in range(8760):
                        energy_balance.shortfall[h] -= min_gen
            except (KeyError, AttributeError):
                continue
        
        return short_taken

    def _process_storage(self, gen_name, pmss_details, energy_balance, option, config) -> Dict:
        """Process storage system dispatch"""
        details = pmss_details[gen_name]
        generator = pmss_details[gen_name]
        
        # Create storage state
        storage_state = self._create_storage_state(details, generator)
        
        # Run storage dispatch simulation
        dispatch_result = self._simulate_storage_dispatch(storage_state, energy_balance, details)
        
        # Track storage names for summary calculations
        config['storage_names'].append(gen_name)
        
        return {
            'facility': gen_name,
            'capacity': storage_state.capacity,
            'capex': details.capex,
            'fixed_om': details.fixed_om,
            'variable_om': details.variable_om, 
            'fuel': details.fuel, 
            'disc_rate': details.disc_rate, 
            'lifetime': details.lifetime,
            'to_meet_load': dispatch_result['total_discharge'],
            'max_mwh': dispatch_result['max_discharge'],
            'max_balance': dispatch_result['max_balance'],
            'facility_type': 'storage',
            'hourly_data': dispatch_result.get('hourly_data') if option == 'D' else None
        }
    
    def _create_storage_state(self, details, generator) -> StorageState:
        """Create storage state object from facility details"""
        capacity = details.capacity * details.multiplier
        
        return StorageState(
            capacity=capacity,
            initial_level=generator.initial * details.multiplier,
            min_level=capacity * details.capacity_min,
            max_level=capacity * details.capacity_max,
            charge_rate=capacity * details.recharge_max,
            discharge_rate=capacity * details.discharge_max,
            charge_efficiency=1 - details.recharge_loss,
            discharge_efficiency=1 - details.discharge_loss,
            parasitic_loss=details.parasitic_loss / 24
        )
    
    def _simulate_storage_dispatch(self, storage_state: StorageState, energy_balance: EnergyBalance, 
                                 details) -> Dict:
        """Simulate hourly storage dispatch"""
        # Initialize storage tracking
        storage_level = storage_state.initial_level
        total_discharge = 0
        max_discharge = 0
        max_balance = storage_level
        
        # Arrays for detailed tracking
        hourly_charge = np.zeros(8760)
        hourly_discharge = np.zeros(8760)
        hourly_balance = np.zeros(8760)
        hourly_losses = np.zeros(8760)
        
        # Operating state tracking
        min_runtime = details.min_runtime
        warm_time = details.warm_time
        in_run = [True, False]  # [discharge_run, warm_run]
        
        if min_runtime > 0 and storage_state.initial_level == 0:
            in_run[0] = False
        
        # Simulate each hour
        for h in range(8760):
            # Apply parasitic losses
            if storage_level > 0:
                parasitic_loss = storage_level * storage_state.parasitic_loss
                storage_level -= parasitic_loss
                hourly_losses[h] -= parasitic_loss
            
            if energy_balance.shortfall[h] < 0:  # Excess generation - charge
                charge_amount = self._calculate_charge(
                    energy_balance.shortfall[h], storage_level, storage_state
                )
                if charge_amount > 0:
                    energy_loss = charge_amount * (1 - storage_state.charge_efficiency)
                    storage_level += charge_amount - energy_loss
                    energy_balance.shortfall[h] += charge_amount  # Reduce excess
                    hourly_charge[h] = charge_amount
                    hourly_losses[h] += energy_loss
                
                # Reset run states during charging
                if min_runtime > 0:
                    in_run[0] = False
                if warm_time > 0:
                    in_run[1] = False
            
            else:  # Shortfall - discharge
                discharge_amount = self._calculate_discharge(
                    energy_balance.shortfall[h], storage_level, storage_state, 
                    h, in_run, min_runtime, warm_time, energy_balance.shortfall
                )
                
                if discharge_amount > 0:
                    energy_loss = discharge_amount * (1 - storage_state.discharge_efficiency)
                    usable_energy = discharge_amount - energy_loss
                    storage_level -= discharge_amount
                    energy_balance.shortfall[h] -= usable_energy
                    
                    hourly_discharge[h] = usable_energy
                    hourly_losses[h] -= energy_loss
                    total_discharge += usable_energy
                    max_discharge = max(max_discharge, usable_energy)
            
            # Update tracking
            hourly_balance[h] = storage_level
            max_balance = max(max_balance, storage_level)
        
        return {
            'total_discharge': total_discharge,
            'max_discharge': max_discharge,
            'max_balance': max_balance,
            'hourly_data': {
                'charge': hourly_charge,
                'discharge': hourly_discharge,
                'balance': hourly_balance,
                'losses': hourly_losses
            }
        }
    
    def _calculate_charge(self, excess_energy, current_level, storage_state: StorageState) -> float:
        """Calculate how much energy to charge"""
        # Available storage space
        available_space = storage_state.max_level - current_level
        if available_space <= 0:
            return 0
        
        # Maximum charge considering efficiency
        max_charge_raw = available_space / storage_state.charge_efficiency
        max_charge_rate = storage_state.charge_rate / storage_state.charge_efficiency
        
        # Take minimum of excess energy, storage space, and charge rate
        charge_amount = min(abs(excess_energy), max_charge_raw, max_charge_rate)
        
        return charge_amount
    
    def _calculate_discharge(self, shortfall, current_level, storage_state: StorageState,
                           hour, in_run, min_runtime, warm_time, all_shortfall) -> float:
        """Calculate how much energy to discharge"""
        if shortfall <= 0:
            return 0
        
        available_energy = current_level - storage_state.min_level
        if available_energy <= 0:
            return 0
        
        # Check minimum run time
        if min_runtime > 0 and not in_run[0]:
            # Look ahead to see if we should start
            if hour + min_runtime <= 8759:
                future_shortfall = all_shortfall[hour:hour + min_runtime]
                if all(sf > 0 for sf in future_shortfall):
                    in_run[0] = True
            
            if not in_run[0]:
                return 0
        
        # Calculate discharge amount
        required_discharge = shortfall / storage_state.discharge_efficiency
        max_discharge = min(
            required_discharge,
            available_energy,
            storage_state.discharge_rate
        )
        
        # Apply warm-up penalty
        if warm_time > 0 and not in_run[1]:
            in_run[1] = True
            max_discharge *= (1 - warm_time)
        
        return max_discharge
    
    def _process_generator(self, gen_name, pmss_details, energy_balance, short_taken, config) -> Dict:
        """Process conventional generator dispatch"""
        details = pmss_details[gen_name]        
        capacity = details.capacity * details.multiplier
        
        # Get capacity limits
        try:
            max_capacity = details.capacity_max * details.multiplier
        except:
            max_capacity = capacity
        
        # Handle minimum generation
        min_gen = short_taken.get(gen_name, 0)
        if min_gen > 0:
            # Add back minimum generation to shortfall for dispatch
            for h in range(8760):
                energy_balance.shortfall[h] += min_gen
        
        # Dispatch generator
        total_generation = 0
        max_generation = 0
        hourly_generation = np.zeros(8760)
        
        for h in range(8760):
            if energy_balance.shortfall[h] >= 0:  # There's a shortfall
                if energy_balance.shortfall[h] >= max_capacity:
                    generation = max_capacity
                    energy_balance.shortfall[h] -= max_capacity
                elif energy_balance.shortfall[h] < min_gen:
                    generation = min_gen
                    energy_balance.shortfall[h] -= min_gen
                else:
                    generation = energy_balance.shortfall[h]
                    energy_balance.shortfall[h] = 0
            else:  # Surplus
                generation = min_gen
                energy_balance.shortfall[h] -= min_gen
            
            hourly_generation[h] = generation
            total_generation += generation
            max_generation = max(max_generation, generation)
        
        return {
            'facility': gen_name,
            'capacity': capacity,
            'capex': details.capex,
            'fixed_om': details.fixed_om,
            'variable_om': details.variable_om, 
            'fuel': details.fuel, 
            'disc_rate': details.disc_rate, 
            'lifetime': details.lifetime,
            'to_meet_load': total_generation,
            'subtotal': total_generation,
            'max_mwh': max_generation,
            'cf': total_generation / capacity / 8760 if capacity > 0 else 0,
            'facility_type': 'generator',
            'hourly_data': hourly_generation
        }
    
    def _calculate_economics(self, renewable_results, dispatch_results, pmss_details) -> Dict:
        """Calculate economic metrics for all facilities"""
        economic_results = {}
        
        all_facilities = renewable_results + dispatch_results
        
        for facility in all_facilities:
            facility_name = facility['facility']
            economics = self._calculate_facility_economics(facility)
            economic_results[facility_name] = economics
        
        return economic_results
    
    def _calculate_facility_economics(self, technology) -> Dict:
        """Calculate economic metrics for a single facility"""
        capacity = technology['capacity']
        generation = technology.get('subtotal', technology.get('to_meet_load', 0))
        
        # Calculate LCOE based on technology type
        if (technology['capex'] > 0 or technology['fixed_om'] > 0 or 
            technology['variable_om'] > 0 or technology['fuel'] > 0):
            
            # Full cost calculation
            capex = capacity * technology['capex']
            opex = (capacity * technology['fixed_om'] + 
                   generation * technology['variable_om'] + 
                   generation * technology['fuel'])
            
            disc_rate = technology['disc_rate'] if technology['disc_rate'] > 0 else self.discount_rate
            lcoe = self._calc_lcoe(generation, capex, opex, disc_rate, technology['lifetime'])
            annual_cost = generation * lcoe
            
            return {
                'lcoe': lcoe,
                'annual_cost': annual_cost,
                'capital_cost': capex,
                'capacity_factor': technology.get('cf', 0)
            }
        
        elif technology.lcoe > 0:
            # Reference LCOE calculation
            cf = technology.lcoe_cf if technology.lcoe_cf > 0 else technology.get('cf', 0)
            annual_cost = technology.lcoe * cf * 8760 * capacity
            
            return {
                'lcoe': technology.lcoe,
                'annual_cost': annual_cost,
                'capital_cost': 0,
                'capacity_factor': cf,
                'reference_lcoe': technology.lcoe,
                'reference_cf': cf
            }
        
        else:
            # No cost facility
            return {
                'lcoe': 0,
                'annual_cost': 0,
                'capital_cost': 0,
                'capacity_factor': technology.get('cf', 0)
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
    
    def _generate_summary_statistics(self, renewable_results, dispatch_results, economic_results, 
                                   energy_balance, config) -> Dict:
        """Generate comprehensive summary statistics"""
        # Combine all results
        all_facilities = renewable_results + dispatch_results
        
        # Calculate totals
        total_capacity = sum(f.get('capacity', 0) for f in all_facilities)
        total_generation = sum(f.get('subtotal', 0) for f in all_facilities)
        total_to_meet_load = sum(f.get('to_meet_load', 0) for f in all_facilities)
        total_cost = sum(economic_results.get(f['facility'], {}).get('annual_cost', 0) for f in all_facilities)
        
        # Calculate shortfall and surplus
        shortfall_sum = sum(max(0, sf) for sf in energy_balance.shortfall)
        surplus_sum = sum(min(0, sf) for sf in energy_balance.shortfall)
        total_load = sum(energy_balance.load_data)
        
        # Calculate percentages
        load_met_pct = (total_load - shortfall_sum) / total_load if total_load > 0 else 0
        surplus_pct = abs(surplus_sum) / total_load if total_load > 0 else 0
        
        # Calculate renewable percentage
        renewable_generation = sum(
            f.get('subtotal', 0) for f in all_facilities 
            if f.get('facility_type') == 'renewable'
        )
        re_pct = renewable_generation / total_generation if total_generation > 0 else 0
        
        return {
            'total_capacity': total_capacity,
            'total_generation': total_generation,
            'total_to_meet_load': total_to_meet_load,
            'total_cost': total_cost,
            'total_load': total_load,
            'shortfall_sum': shortfall_sum,
            'surplus_sum': surplus_sum,
            'load_met_pct': load_met_pct,
            'surplus_pct': surplus_pct,
            'renewable_pct': re_pct,
            'lcoe': total_cost / total_to_meet_load if total_to_meet_load > 0 else 0,
            'facilities': all_facilities
        }
    
    def _create_output_arrays(self, summary_stats, dispatch_results, option, config) -> Tuple[np.ndarray, Optional[np.ndarray]]:
        """Create structured numpy arrays for output"""
        # Create summary array
        facilities = summary_stats['facilities']
        
        # Define summary data structure
        summary_dtype = [
            ('facility', 'U50'),
            ('capacity', 'f8'),
            ('to_meet_load', 'f8'),
            ('subtotal', 'f8'),
            ('cf', 'f8'),
            ('cost_per_year', 'f8'),
            ('lcoe', 'f8'),
            ('max_mwh', 'f8'),
            ('facility_type', 'U20')
        ]
        
        summary_array = np.zeros(len(facilities), dtype=summary_dtype)
        
        for i, facility in enumerate(facilities):
            summary_array[i]['facility'] = facility.get('facility', '')
            summary_array[i]['capacity'] = facility.get('capacity', 0)
            summary_array[i]['to_meet_load'] = facility.get('to_meet_load', 0)
            summary_array[i]['subtotal'] = facility.get('subtotal', 0)
            summary_array[i]['cf'] = facility.get('cf', 0)
            summary_array[i]['max_mwh'] = facility.get('max_mwh', 0)
            summary_array[i]['facility_type'] = facility.get('facility_type', '')
        
        # Create hourly array if detailed output requested
        hourly_array = None
        if option == 'D':
            hourly_array = self._create_hourly_array(dispatch_results, config)
        
        return summary_array, hourly_array
    
    def _create_hourly_array(self, dispatch_results, config) -> np.ndarray:
        """Create hourly data array for detailed output"""
        # This would include hourly generation data for all facilities
        # Implementation depends on specific requirements
        num_hours = 8760
        num_facilities = len(dispatch_results)
        
        hourly_array = np.zeros((num_hours, num_facilities + 2))  # +2 for hour and load
        
        # Fill with hourly data from dispatch results
        for i, result in enumerate(dispatch_results):
            if 'hourly_data' in result and result['hourly_data'] is not None:
                hourly_array[:, i + 2] = result['hourly_data']
        
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
            'surplus_pct': summary_stats['surplus_pct'],
            'renewable_pct': summary_stats['renewable_pct'],
            'system_lcoe': summary_stats['lcoe'],
            'storage_facilities': config['storage_names'],
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

# Additional utility classes and functions

class FacilityProcessor:
    """Specialized processor for different facility types"""
    
    def __init__(self, pmss_details):
        self.pmss_details = pmss_details
    
    def process_renewable(self, facility_name, details, hourly_data, energy_balance):
        """Process renewable energy facility"""
        return {
            'name': facility_name,
            'type': 'renewable',
            'capacity': details.capacity * details.multiplier,
            'generation_profile': hourly_data[details.merit_order] * details.multiplier,
            'contribution_to_load': energy_balance.facility_contributions.get(facility_name, 0)
        }
    
    def process_storage(self, facility_name, details, energy_balance, option):
        """Process storage facility with detailed state tracking"""
        generator = self.pmss_details[facility_name]
        
        # Initialize storage parameters
        storage_params = self._get_storage_parameters(details, generator)
        
        # Run storage simulation
        storage_results = self._simulate_storage_operation(storage_params, energy_balance, option)
        
        return storage_results
    
    def _get_storage_parameters(self, details):
        """Extract storage parameters from configuration"""
        capacity = details.capacity * details.multiplier
        
        return {
            'capacity': capacity,
            'initial_soc': details.initial,
            'min_soc': details.capacity_min,
            'max_soc': details.capacity_max,
            'charge_rate': capacity * details.recharge_max,
            'discharge_rate': capacity * details.discharge_max,
            'charge_efficiency': 1 - details.recharge_loss,
            'discharge_efficiency': 1 - details.discharge_loss,
            'parasitic_loss_rate': details.parasitic_loss,
            'min_runtime': details.min_runtime,
            'warm_time': details.warm_time
        }
    
    def _simulate_storage_operation(self, params, energy_balance, option):
        """Detailed storage operation simulation"""
        # Implementation of sophisticated storage dispatch algorithm
        # This would include all the complex storage logic from the original
        
        soc = params['initial_soc'] * params['capacity']  # State of charge in MWh
        hourly_operations = []
        total_discharge = 0
        total_charge = 0
        max_discharge_power = 0
        max_soc = soc
        
        # Operating state tracking
        discharge_run_active = True if soc > 0 else False
        warm_run_active = False
        
        for hour in range(8760):
            hour_operation = {
                'hour': hour,
                'initial_soc': soc,
                'shortfall': energy_balance.shortfall[hour],
                'charge': 0,
                'discharge': 0,
                'losses': 0,
                'final_soc': soc
            }
            
            # Apply parasitic losses
            if soc > 0:
                parasitic_loss = soc * params['parasitic_loss_rate']
                soc -= parasitic_loss
                hour_operation['losses'] += parasitic_loss
            
            if energy_balance.shortfall[hour] < 0:  # Excess energy - charge
                excess = abs(energy_balance.shortfall[hour])
                
                # Calculate maximum charge possible
                available_capacity = params['capacity'] * params['max_soc'] - soc
                max_charge_energy = min(
                    excess,
                    available_capacity / params['charge_efficiency'],
                    params['charge_rate']
                )
                
                if max_charge_energy > 0:
                    energy_to_storage = max_charge_energy * params['charge_efficiency']
                    charge_loss = max_charge_energy - energy_to_storage
                    
                    soc += energy_to_storage
                    energy_balance.shortfall[hour] += max_charge_energy  # Reduce excess
                    
                    hour_operation['charge'] = max_charge_energy
                    hour_operation['losses'] += charge_loss
                    total_charge += max_charge_energy
                
                # Reset operating states during charging
                discharge_run_active = False
                warm_run_active = False
            
            elif energy_balance.shortfall[hour] > 0:  # Energy needed - discharge
                shortfall = energy_balance.shortfall[hour]
                
                # Check minimum run time
                if params['min_runtime'] > 0 and not discharge_run_active:
                    # Look ahead to see if sustained discharge is needed
                    if self._check_sustained_shortfall(energy_balance.shortfall, hour, params['min_runtime']):
                        discharge_run_active = True
                
                if discharge_run_active:
                    # Calculate available energy for discharge
                    available_energy = soc - params['capacity'] * params['min_soc']
                    
                    if available_energy > 0:
                        # Calculate discharge amount
                        energy_needed_from_storage = shortfall / params['discharge_efficiency']
                        max_discharge_energy = min(
                            energy_needed_from_storage,
                            available_energy,
                            params['discharge_rate']
                        )
                        
                        # Apply warm-up penalty if first hour of operation
                        if params['warm_time'] > 0 and not warm_run_active:
                            warm_run_active = True
                            max_discharge_energy *= (1 - params['warm_time'])
                        
                        if max_discharge_energy > 0:
                            discharge_loss = max_discharge_energy * (1 - params['discharge_efficiency'])
                            usable_energy = max_discharge_energy - discharge_loss
                            
                            soc -= max_discharge_energy
                            energy_balance.shortfall[hour] -= usable_energy
                            
                            hour_operation['discharge'] = usable_energy
                            hour_operation['losses'] += discharge_loss
                            total_discharge += usable_energy
                            max_discharge_power = max(max_discharge_power, usable_energy)
            
            hour_operation['final_soc'] = soc
            max_soc = max(max_soc, soc)
            
            if option == 'D':  # Store detailed hourly data
                hourly_operations.append(hour_operation)
        
        return {
            'facility_type': 'storage',
            'total_discharge': total_discharge,
            'total_charge': total_charge,
            'max_discharge_power': max_discharge_power,
            'max_soc': max_soc,
            'final_soc': soc,
            'hourly_operations': hourly_operations if option == 'D' else None
        }
    
    def _check_sustained_shortfall(self, shortfall_array, start_hour, min_duration):
        """Check if shortfall persists for minimum duration"""
        end_hour = min(start_hour + min_duration, len(shortfall_array))
        for h in range(start_hour, end_hour):
            if shortfall_array[h] <= 0:
                return False
        return True

class EconomicsCalculator:
    """Specialized calculator for economic metrics"""
    
    def __init__(self, carbon_price=0, discount_rate=0.05):
        self.carbon_price = carbon_price
        self.discount_rate = discount_rate
    
    def calculate_facility_economics(self, facility_data, generator_specs):
        """Calculate comprehensive economic metrics for a facility"""
        capacity = facility_data['capacity']
        annual_generation = facility_data.get('annual_generation', 0)
        
        # Calculate LCOE based on cost structure
        if self._has_detailed_costs(generator_specs):
            return self._calculate_detailed_lcoe(capacity, annual_generation, generator_specs)
        elif generator_specs.lcoe > 0:
            return self._calculate_reference_lcoe(capacity, annual_generation, generator_specs)
        else:
            return self._calculate_zero_cost(capacity, annual_generation)
    
    def _has_detailed_costs(self, generator_specs):
        """Check if generator has detailed cost breakdown"""
        return (generator_specs.capex > 0 or 
                generator_specs.fixed_om > 0 or 
                generator_specs.variable_om > 0 or 
                generator_specs.fuel > 0)
    
    def _calculate_detailed_lcoe(self, capacity, annual_generation, generator_specs):
        """Calculate LCOE from detailed cost components"""
        # Capital costs
        capex = capacity * generator_specs.capex
        
        # Operating costs
        fixed_om = capacity * generator_specs.fixed_om
        variable_om = annual_generation * generator_specs.variable_om
        fuel_cost = annual_generation * generator_specs.fuel
        
        # Discount rate
        disc_rate = generator_specs.disc_rate if generator_specs.disc_rate > 0 else self.discount_rate
        
        # Annualized capital cost
        if disc_rate > 0:
            capital_recovery_factor = (disc_rate * (1 + disc_rate) ** generator_specs.lifetime / 
                                     ((1 + disc_rate) ** generator_specs.lifetime - 1))
            annual_capex = capex * capital_recovery_factor
        else:
            annual_capex = capex / generator_specs.lifetime
        
        total_annual_cost = annual_capex + fixed_om + variable_om + fuel_cost
        
        lcoe = total_annual_cost / annual_generation if annual_generation > 0 else 0
        
        return {
            'lcoe': lcoe,
            'annual_cost': total_annual_cost,
            'capital_cost': capex,
            'annual_capex': annual_capex,
            'fixed_om': fixed_om,
            'variable_om': variable_om,
            'fuel_cost': fuel_cost,
            'capacity_factor': annual_generation / (capacity * 8760) if capacity > 0 else 0
        }
    
    def _calculate_reference_lcoe(self, capacity, annual_generation, generator_specs):
        """Calculate economics based on reference LCOE"""
        capacity_factor = generator_specs.lcoe_cf if generator_specs.lcoe_cf > 0 else \
                         (annual_generation / (capacity * 8760) if capacity > 0 else 0)
        
        annual_cost = generator_specs.lcoe * capacity_factor * 8760 * capacity
        
        return {
            'lcoe': generator_specs.lcoe,
            'annual_cost': annual_cost,
            'capital_cost': 0,
            'reference_lcoe': generator_specs.lcoe,
            'reference_cf': capacity_factor,
            'capacity_factor': capacity_factor
        }
    
    def _calculate_zero_cost(self, capacity, annual_generation):
        """Calculate metrics for zero-cost facilities"""
        return {
            'lcoe': 0,
            'annual_cost': 0,
            'capital_cost': 0,
            'capacity_factor': annual_generation / (capacity * 8760) if capacity > 0 else 0
        }
    
    def calculate_emissions(self, annual_generation, emission_factor):
        """Calculate annual emissions and costs"""
        annual_emissions = annual_generation * emission_factor
        annual_emission_cost = annual_emissions * self.carbon_price
        
        return {
            'annual_emissions': annual_emissions,
            'annual_emission_cost': annual_emission_cost,
            'emission_factor': emission_factor
        }
    
    def calculate_system_metrics(self, facility_results):
        """Calculate system-wide economic metrics"""
        total_cost = sum(f.get('annual_cost', 0) for f in facility_results)
        total_generation = sum(f.get('annual_generation', 0) for f in facility_results)
        total_capacity = sum(f.get('capacity', 0) for f in facility_results)
        
        system_lcoe = total_cost / total_generation if total_generation > 0 else 0
        average_cf = total_generation / (total_capacity * 8760) if total_capacity > 0 else 0
        
        return {
            'system_lcoe': system_lcoe,
            'total_annual_cost': total_cost,
            'total_generation': total_generation,
            'total_capacity': total_capacity,
            'average_capacity_factor': average_cf
        }

class ResultsFormatter:
    """Formats results into various output formats"""

    def __init__(self):
        self.summary_columns = [
            'facility', 'capacity', 'to_meet_load', 'subtotal', 'cf', 
            'cost_per_year', 'lcoe', 'emissions', 'max_mwh'
        ]

    def create_summary_array(self, facility_results, economic_results):
        """Create structured numpy array for summary results"""
        num_facilities = len(facility_results)
        
        # Define structured array dtype
        dtype = [
            ('facility', 'U50'),
            ('capacity', 'f8'),
            ('to_meet_load', 'f8'),
            ('subtotal', 'f8'),
            ('cf', 'f8'),
            ('cost_per_year', 'f8'),
            ('lcoe', 'f8'),
            ('emissions', 'f8'),
            ('max_mwh', 'f8'),
            ('facility_type', 'U20')
        ]
        
        summary_array = np.zeros(num_facilities, dtype=dtype)
        
        for i, facility in enumerate(facility_results):
            facility_name = facility['name']
            economics = economic_results.get(facility_name, {})
            
            summary_array[i] = (
                facility_name,
                facility.get('capacity', 0),
                facility.get('contribution_to_load', 0),
                facility.get('total_generation', 0),
                economics.get('capacity_factor', 0),
                economics.get('annual_cost', 0),
                economics.get('lcoe', 0),
                facility.get('annual_emissions', 0),
                facility.get('max_output', 0),
                facility.get('type', 'unknown')
            )
        
        return summary_array

    def create_hourly_array(self, facility_results, include_storage_detail=True):
        """Create hourly data array for detailed analysis"""
        hours = 8760
        
        # Count data columns needed
        base_columns = ['hour', 'load']
        facility_columns = []
        
        for facility in facility_results:
            if facility['type'] == 'storage' and include_storage_detail:
                facility_columns.extend([
                    f"{facility['name']}_charge",
                    f"{facility['name']}_discharge", 
                    f"{facility['name']}_soc"
                ])
            else:
                facility_columns.append(facility['name'])
        
        all_columns = base_columns + facility_columns
        hourly_array = np.zeros((hours, len(all_columns)))
        
        # Fill hourly data
        for h in range(hours):
            hourly_array[h, 0] = h + 1  # Hour number
            
            col_idx = 2  # Start after hour and load columns
            for facility in facility_results:
                if facility['type'] == 'storage' and include_storage_detail:
                    # Storage detailed data
                    operations = facility.get('hourly_operations', [])
                    if h < len(operations):
                        hourly_array[h, col_idx] = operations[h].get('charge', 0)
                        hourly_array[h, col_idx + 1] = operations[h].get('discharge', 0)
                        hourly_array[h, col_idx + 2] = operations[h].get('final_soc', 0)
                    col_idx += 3
                else:
                    # Regular facility data
                    profile = facility.get('generation_profile', np.zeros(hours))
                    if h < len(profile):
                        hourly_array[h, col_idx] = profile[h]
                    col_idx += 1
        
        return hourly_array, all_columns
