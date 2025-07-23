# run_powermatch.py
from django.contrib.auth.decorators import login_required
import numpy as np
from siren_web.database_operations import get_scenario_by_title, delete_analysis_scenario, fetch_module_settings_data, \
    fetch_scenario_settings_data, fetch_technology_attributes, fetch_supplyfactors_data
from siren_web.models import Analysis, ScenariosSettings
from typing import Dict, Any, Tuple
from .balance_grid_load import Technology, PowerMatchProcessor, DispatchResults


def save_analysis(i, sp_data, metadata, scenario, variation, stage):
    """
    Insert power system analysis data into the Analysis model.
    
    Args:
        i: Iteration number (used for static variables insertion)
        sp_data: Numpy structured array with technology data
        metadata: Dictionary containing system totals and parameters
        scenario_obj: Scenario model instance
        variation: Variation name string
        stage: Stage number
    """
    
    # Define the mapping from sp_data fields to Analysis records
    field_mappings = [
        ('capacity_mw', 'Capacity', 'MW'),
        ('generation_mwh', 'Generation', 'MWh'),
        ('to_meet_load_mwh', 'To Meet Load', 'MWh'),
        ('capacity_factor', 'CF', '%'),
        ('annual_cost', 'Cost', '$/yr'),
        ('lcog_per_mwh', 'LCOG Cost', '$/MWh'),
        ('lcoe_per_mwh', 'LCOE Cost', '$/MWh'),
        ('emissions_tco2e', 'Emissions', 'tCO2e'),
        ('emissions_cost', 'Emissions Cost', '$'),
        ('lcoe_with_co2_per_mwh', 'LCOE with CO2 Cost', '$/MWh'),
        ('max_generation_mw', 'Max Generation', 'MW'),
        ('max_balance', 'Max Balance', 'MW'),
        ('capital_cost', 'Capital Cost', '$'),
        ('lifetime_cost', 'Lifetime Cost', '$'),
        ('lifetime_emissions', 'Lifetime Emissions', 'tCO2e'),
        ('lifetime_emissions_cost', 'Lifetime Emissions Cost', '$'),
        ('area_km2', 'Area', 'km²'),
        ('reference_lcoe', 'Reference LCOE', '$/MWh'),
        ('reference_cf', 'Reference CF', '%'),
    ]

    # Insert technology-specific data
    analysis_records = []
    scenario_obj = get_scenario_by_title(scenario)

    for row in sp_data:
        technology_name = row['technology']
        
        for field_name, heading, units in field_mappings:
            quantity = float(row[field_name])
            
            # Convert percentage values (capacity factor and reference CF are stored as decimal)
            if heading in ['CF', 'Reference CF']:
                quantity = quantity * 100  # Convert to percentage
            
            analysis_records.append(Analysis(
                idscenarios=scenario_obj,
                heading=heading,
                component=technology_name,
                variation=variation,
                stage=stage,
                quantity=quantity,
                units=units
            ))
    
    # Insert system totals from metadata
    system_totals = metadata.get('system_totals', {})
    system_mappings = [
        ('total_capacity_mw', 'Capacity', 'Total', 'MW'),
        ('total_generation_mwh', 'Generation', 'Total', 'MWh'),
        ('total_to_meet_load_mwh', 'To Meet Load', 'Total', 'MWh'),
        ('total_annual_cost', 'Annual Cost', 'Total', '$/yr'),
        ('total_emissions_tco2e', 'Emissions', 'Total', 'tCO2e'),
        ('total_emissions_cost', 'Emissions Cost', 'Total', '$'),
        ('total_capital_cost', 'Capital Cost', 'Total', '$'),
        ('total_lifetime_cost', 'Lifetime Cost', 'Total', '$'),
        ('total_lifetime_emissions', 'Lifetime Emissions', 'Total', 'tCO2e'),
        ('total_lifetime_emissions_cost', 'Lifetime Emissions Cost', 'Total', '$'),
        ('total_area_km2', 'Area', 'Total', 'km²'),
    ]
    
    for field_name, heading, component, units in system_mappings:
        if field_name in system_totals:
            quantity = float(system_totals[field_name])
            analysis_records.append(Analysis(
                idscenarios=scenario_obj,
                heading=heading,
                component=component,
                variation=variation,
                stage=stage,
                quantity=quantity,
                units=units
            ))
    
    # Insert system-level statistics from metadata
    system_stats = [
        ('total_load_mwh', 'Load', 'Load Analysis', 'MWh'),
        ('load_met_pct', '% Load Met', 'Load Analysis', '%'),
        ('total_shortfall_mwh', 'Shortfall', 'Load Analysis', 'MWh'),
        ('max_shortfall_mw', 'Max Shortfall', 'Load Analysis', 'MW'),
        ('total_curtailment_mwh', 'Curtailment', 'Load Analysis', 'MWh'),
        ('curtailment_pct', '% Curtailment', 'Load Analysis', '%'),
        ('renewable_pct', '% Renewable', 'Load Analysis', '%'),
        ('renewable_load_pct', '% Renewable of Load', 'Load Analysis', '%'),
        ('storage_pct', '% Storage', 'Load Analysis', '%'),
        ('system_lcoe', 'System LCOE', 'System Economics', '$/MWh'),
        ('system_lcoe_with_co2', 'System LCOE with CO2', 'System Economics', '$/MWh'),
    ]
    
    for field_name, heading, component, units in system_stats:
        if field_name in metadata:
            quantity = float(metadata[field_name])
            
            # Convert percentage values (stored as decimals in metadata)
            if units == '%' and quantity <= 1.0:
                quantity = quantity * 100
            
            analysis_records.append(Analysis(
                idscenarios=scenario_obj,
                heading=heading,
                component=component,
                variation=variation,
                stage=stage,
                quantity=quantity,
                units=units
            ))
    
    # Bulk create all records for better performance
    Analysis.objects.bulk_create(analysis_records)
    
    # Insert static variables into ScenariosSettings on first iteration
    if i == 0:
        static_variables = [
            ('carbon_price', metadata.get('carbon_price', 0), '$/tCO2e'),
            ('discount_rate', metadata.get('discount_rate', 0) * 100, '%'),  # Convert to percentage
            ('max_lifetime', metadata.get('max_lifetime', 0), 'years'),
        ]
        
        settings_records = []
        for parameter, value, units in static_variables:
            settings_records.append(ScenariosSettings(
                idscenarios=scenario_obj,
                sw_context='Powermatch',
                parameter=parameter,
                value=float(value),
                units=units,
            ))
        
        ScenariosSettings.objects.bulk_create(settings_records)

def fetch_analysis(scenario, variation: str, stage: int) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    Fetch power system analysis data from the Analysis model and reconstruct sp_data and metadata.
    
    Args:
        scenario_obj: Scenario model instance
        variation: Variation name string
        stage: Stage number
        
    Returns:
        Tuple of (sp_data, metadata) where:
        - sp_data: Numpy structured array with technology data
        - metadata: Dictionary containing system totals and parameters
    """
    scenario_obj = get_scenario_by_title(scenario)
    
    # Fetch all analysis records for this scenario/variation/stage
    analysis_records = Analysis.objects.filter(
        idscenarios=scenario_obj,
        variation=variation,
        stage=stage
    ).values('heading', 'component', 'quantity', 'units')
    
    # Organize data by component and heading
    data_by_component = {}
    system_totals = {}
    load_analysis = {}
    system_economics = {}
    
    for record in analysis_records:
        heading = record['heading']
        component = record['component']
        quantity = record['quantity']
        units = record['units']
        
        if component == 'System Total':
            system_totals[heading] = quantity
        elif component == 'Load Analysis':
            load_analysis[heading] = quantity
        elif component == 'System Economics':
            system_economics[heading] = quantity
        else:
            # Technology-specific data
            if component not in data_by_component:
                data_by_component[component] = {}
            data_by_component[component][heading] = quantity
    
    # Define the reverse mapping from Analysis headings to sp_data fields
    heading_to_field = {
        'Capacity': 'capacity_mw',
        'Generation': 'generation_mwh',
        'To Meet Load': 'to_meet_load_mwh',
        'CF': 'capacity_factor',
        'Cost': 'annual_cost',
        'LCOG Cost': 'lcog_per_mwh',
        'LCOE Cost': 'lcoe_per_mwh',
        'Emissions': 'emissions_tco2e',
        'Emissions Cost': 'emissions_cost',
        'LCOE with CO2 Cost': 'lcoe_with_co2_per_mwh',
        'Max Generation': 'max_generation_mw',
        'Max Balance': 'max_balance',
        'Capital Cost': 'capital_cost',
        'Lifetime Cost': 'lifetime_cost',
        'Lifetime Emissions': 'lifetime_emissions',
        'Lifetime Emissions Cost': 'lifetime_emissions_cost',
        'Area': 'area_km2',
        'Reference LCOE': 'reference_lcoe',
        'Reference CF': 'reference_cf',
    }
    
    # Create sp_data structured array
    sp_data_dtype = [
        ('technology', '<U50'),
        ('capacity_mw', '<f8'),
        ('generation_mwh', '<f8'),
        ('to_meet_load_mwh', '<f8'),
        ('capacity_factor', '<f8'),
        ('annual_cost', '<f8'),
        ('lcog_per_mwh', '<f8'),
        ('lcoe_per_mwh', '<f8'),
        ('emissions_tco2e', '<f8'),
        ('emissions_cost', '<f8'),
        ('lcoe_with_co2_per_mwh', '<f8'),
        ('max_generation_mw', '<f8'),
        ('max_balance', '<f8'),
        ('capital_cost', '<f8'),
        ('lifetime_cost', '<f8'),
        ('lifetime_emissions', '<f8'),
        ('lifetime_emissions_cost', '<f8'),
        ('area_km2', '<f8'),
        ('reference_lcoe', '<f8'),
        ('reference_cf', '<f8'),
    ]
    
    # Get technology names (excluding system totals, load analysis, etc.)
    technology_names = [comp for comp in data_by_component.keys() 
                       if comp not in ['System Total', 'Load Analysis', 'System Economics']]
    
    # Create numpy structured array
    sp_data = np.zeros(len(technology_names), dtype=sp_data_dtype)
    
    for i, tech_name in enumerate(technology_names):
        sp_data[i]['technology'] = tech_name
        tech_data = data_by_component[tech_name]
        
        for heading, field_name in heading_to_field.items():
            if heading in tech_data:
                value = tech_data[heading]
                # Convert percentage back to decimal for capacity factor
                if heading == 'CF':
                    value = value / 100.0
                sp_data[i][field_name] = value
            else:
                sp_data[i][field_name] = 0.0
    
    # Reconstruct metadata
    metadata = {}
    
    # Get static variables from ScenariosSettings
    settings_records = ScenariosSettings.objects.filter(
        idscenarios=scenario_obj,
        sw_context='Powermatch'
    ).values('parameter', 'value', 'units')
    
    for record in settings_records:
        param = record['parameter']
        value = record['value']
        if param == 'carbon_price':
            metadata['carbon_price'] = value
        elif param == 'discount_rate':
            metadata['discount_rate'] = float(value.rstrip('%')) / 100.0
        elif param == 'max_lifetime':
            metadata['max_lifetime'] = value
    
    # System totals mapping
    system_totals_mapping = {
        'Capacity': 'total_capacity_mw',
        'Generation': 'total_generation_mwh',
        'To Meet Load': 'total_to_meet_load_mwh',
        'Annual Cost': 'total_annual_cost',
        'Emissions': 'total_emissions_tco2e',
        'Emissions Cost': 'total_emissions_cost',
        'Capital Cost': 'total_capital_cost',
        'Lifetime Cost': 'total_lifetime_cost',
        'Lifetime Emissions': 'total_lifetime_emissions',
        'Lifetime Emissions Cost': 'total_lifetime_emissions_cost',
        'Area': 'total_area_km2',
    }
    
    metadata['system_totals'] = {}
    for heading, field_name in system_totals_mapping.items():
        if heading in system_totals:
            metadata['system_totals'][field_name] = system_totals[heading]
    
    # Load analysis mapping
    load_analysis_mapping = {
        'Total Load': 'total_load_mwh',
        '% Load Met': 'load_met_pct',
        'Shortfall': 'total_shortfall_mwh',
        'Max Shortfall': 'max_shortfall_mw',
        'Curtailment': 'total_curtailment_mwh',
        '% Curtailment': 'curtailment_pct',
        '% Renewable': 'renewable_pct',
        '% Renewable of Load': 'renewable_load_pct',
        '% Storage': 'storage_pct',
    }
    
    for heading, field_name in load_analysis_mapping.items():
        if heading in load_analysis:
            value = load_analysis[heading]
            # Convert percentages back to decimals
            if heading.startswith('%') and value > 1.0:
                value = value / 100.0
            metadata[field_name] = value
    
    # System economics mapping
    economics_mapping = {
        'System LCOE': 'system_lcoe',
        'System LCOE with CO2': 'system_lcoe_with_co2',
    }
    
    for heading, field_name in economics_mapping.items():
        if heading in system_economics:
            metadata[field_name] = system_economics[heading]
    
    # Set default values for fields that might not be stored
    metadata.setdefault('processing_time', 0.0)
    metadata.setdefault('year', '2024')
    metadata.setdefault('option', 'S')
    metadata.setdefault('sender_name', 'Retrieved')
    metadata.setdefault('correlation_data', None)
    metadata.setdefault('max_shortfall_hour', 1)
    metadata.setdefault('adjusted_lcoe', True)
    metadata.setdefault('remove_cost', True)
    metadata.setdefault('surplus_sign', 1)
    
    # Technology classifications (these would need to be determined based on your system)
    # You might want to store these in the database or determine them dynamically
    metadata.setdefault('storage_technologies', ['Battery (8hr)', 'PHES (24hr)'])
    metadata.setdefault('renewable_technologies', ['Onshore Wind', 'Fixed PV', 'Single Axis PV', 'Battery (8hr)', 'PHES (24hr)', 'Biomass'])
    metadata.setdefault('generator_technologies', [tech for tech in technology_names])
    metadata.setdefault('underlying_technologies', [])
    
    return sp_data, metadata
    
def submit_powermatch(demand_year, scenario, 
                      option, stages, variation_inst, save_data=False):
    scenario_settings = fetch_scenario_settings_data(scenario)
    if not scenario_settings:
        scenario_settings = fetch_module_settings_data('Powermatch')
    if save_data:
        load_and_supply = \
            fetch_supplyfactors_data(demand_year, scenario)
        technology_attributes = \
            fetch_technology_attributes(demand_year, scenario)
    
    for i in range(stages):
                
        # For variations adjust the dimension up by the step value each iteration
        if variation_inst:
            technology = variation_inst.idtechnologies
            dimension = variation_inst.dimension
            step = variation_inst.step
            technology_name = technology.technology_name
            if dimension == 'multiplier':
                technology_attributes[technology_name].multiplier += step
            elif dimension == 'capex':
                technology_attributes[technology_name].capex += step
            elif dimension == 'fom':
                technology_attributes[technology_name].fixed_om += step
            elif dimension == 'vom':
                technology_attributes[technology_name].variable_om += step
            elif dimension == 'lifetime':
                technology_attributes[technology_name].lifetime += step

        if option == 'D':
            action = 'Detail'
        else:
            action = 'Summary'
        # Run PowerMatch
        if save_data or option == 'D':
            pm = PowerMatchProcessor(scenario_settings)
            dispatch_results = pm.matchSupplytoLoad(
                demand_year, option, action, technology_attributes, load_and_supply
            )
            sp_data = dispatch_results.summary_data
            metadata = dispatch_results.metadata
            hourly_data = dispatch_results.hourly_data
        else:
            sp_data, metadata = fetch_analysis(scenario, 'Baseline', 0)
            hourly_data = None
            dispatch_results = DispatchResults(
                summary_data=sp_data,
                metadata=metadata,
                hourly_data=hourly_data
            )
        
        # Work with hourly data (if available)
        if hourly_data is not None:
            # Example: Plot first week (hours 0-167)
            print(f"Hourly data available for {hourly_data.shape[0]} hours, {hourly_data.shape[1]} columns")
    
        # Save results if not detailed option
        if save_data:
            if variation_inst:
                variation = variation_inst.variation_name
                Stage = i + 1
            else:
                scenario_obj = get_scenario_by_title(scenario)
                delete_analysis_scenario(scenario_obj)
                variation = 'Baseline'
                Stage = 0
            if save_data:
                save_analysis(i, sp_data, metadata, scenario, variation, Stage)

        return dispatch_results

def submit_powermatch_with_progress(demand_year, scenario, option, stages, 
                                   variation_inst, save_data, progress_handler) -> DispatchResults:
    """Enhanced submit_powermatch with progress reporting"""
    if progress_handler:
        progress_handler.update(10, "Initializing PowerMatch submission...")
    try:
        if progress_handler:
            progress_handler.update(12, "Loading scenario settings...")
        scenario_settings = fetch_scenario_settings_data(scenario)
        if not scenario_settings:
            scenario_settings = fetch_module_settings_data('Powermatch')
        
        if save_data or option == 'D':
            if progress_handler:
                progress_handler.update(20, "Loading supply factors data...")
            load_and_supply = fetch_supplyfactors_data(demand_year, scenario)
            if progress_handler:
                progress_handler.update(30, "Loading technology attributes data...")
            technology_attributes = fetch_technology_attributes(demand_year, scenario)
        if progress_handler:
            progress_handler.update(35, "Processing analysis stages...")

        # Determine action type
        if option == 'D':
            action = 'Detail'
        else:
            action = 'Summary'
        
        # Run PowerMatch with enhanced progress tracking
        if save_data or option == 'D':
            if progress_handler:
                progress_handler.update(message="Running PowerMatch analysis...")
                pm = PowerMatchProcessor(
                    scenario_settings, 
                    progress_handler=progress_handler,
                    event_callback=lambda: progress_handler.update(increment=False)
                )
            else:
                pm = PowerMatchProcessor(
                    scenario_settings, 
                    progress_handler=None,
                    event_callback=None
                )

        for i in range(stages):
            stage_progress = 35 + (50 * (i + 1) / stages)
            if progress_handler:
                progress_handler.update(int(stage_progress), f"Processing stage {i+1} of {stages}...")
            
            # For variations adjust the dimension up by the step value each iteration
            if variation_inst:
                technology = variation_inst.idtechnologies
                dimension = variation_inst.dimension
                step = variation_inst.step
                technology_name = technology.technology_name
                if dimension == 'multiplier':
                    technology_attributes[technology_name].multiplier += step
                elif dimension == 'capex':
                    technology_attributes[technology_name].capex += step
                elif dimension == 'fom':
                    technology_attributes[technology_name].fixed_om += step
                elif dimension == 'vom':
                    technology_attributes[technology_name].variable_om += step
                elif dimension == 'lifetime':
                    technology_attributes[technology_name].lifetime += step
                
                dispatch_results = pm.matchSupplytoLoad(
                    demand_year, option, action, technology_attributes, load_and_supply
                )
                sp_data = dispatch_results.summary_data
                metadata = dispatch_results.metadata
                hourly_data = dispatch_results.hourly_data
            else:
                from powermatchui.views.exec_powermatch import fetch_analysis
                if progress_handler:
                    progress_handler.update(80, "Fetching existing analysis...")
                sp_data, metadata = fetch_analysis(scenario, 'Baseline', 0)
                hourly_data = None
                dispatch_results = DispatchResults(
                    summary_data=sp_data,
                    metadata=metadata,
                    hourly_data=hourly_data
                )
        
            # Save results if requested
            if save_data:
                if progress_handler:
                    progress_handler.update(85, "Saving analysis results...")
                if variation_inst:
                    variation = variation_inst.variation_name
                    Stage = i + 1
                else:
                    variation = 'Baseline'
                    Stage = 0
                    scenario_obj = get_scenario_by_title(scenario)
                    delete_analysis_scenario(scenario_obj)
                save_analysis(i, sp_data, metadata, scenario, variation, Stage)
        
        if progress_handler:
            progress_handler.update(100, "Analysis complete!")
        return dispatch_results
    
    except Exception as e:
        if progress_handler:
            progress_handler.update(
                step=progress_handler.current_step, 
                message=f"Error: {str(e)}", 
                increment=False
            )
        raise e