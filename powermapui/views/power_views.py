from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.conf import settings
import logging

from siren_web.database_operations import (
    fetch_full_facilities_data, 
    fetch_module_settings_data, 
    fetch_scenario_settings_data, 
    fetch_all_config_data
)
from siren_web.models import facilities, supplyfactors, Scenarios
from pathlib import Path
from powermapui.views.wasceneweb import WASceneWeb as WAScene
from powermapui.views.powermodelweb import PowerModelWeb as PowerModel

# Import the SAM processor
from powermapui.views.sam_resource_processor import SAMResourceProcessor, SAMError, WeatherFileError, SimulationResults

logger = logging.getLogger(__name__)

@login_required
def generate_power(request):
    """
    Generate power for all facilities using SAM for renewables and traditional models for others
    """
    demand_year = request.session.get('demand_year', '')
    scenario = request.session.get('scenario', '')
    config_file = request.session.get('config_file')
    
    # Check if this is just displaying the confirmation page
    if request.method == 'GET' and not request.GET.get('confirm'):
        # Show the confirmation template first
        context = {
            'demand_year': demand_year,
            'scenario': scenario,
            'config_file': config_file,
        }
        return render(request, 'generate_power.html', context)
    
    # Add refresh parameter - can come from POST or GET with confirm
    refresh_supply_factors = (
        request.POST.get('refresh_supply_factors') == 'true' or 
        request.GET.get('refresh_supply_factors') == 'true'
    )
    
    success_message = ""
    
    if not demand_year:
        success_message = "Set a demand year, scenario and config first."
    else:
        try:
            # Get configuration and settings
            scenario_settings = fetch_module_settings_data('Powermap')
            if not scenario_settings:
                scenario_settings = fetch_scenario_settings_data(scenario)
                
            facilities_list = fetch_full_facilities_data(demand_year, scenario)
            config = fetch_all_config_data(request)
            
            # Process renewable facilities with SAM - pass refresh flag
            sam_processed_count, traditional_processed_count, skipped_count = process_facilities(
                config, facilities_list, demand_year, scenario, refresh_supply_factors
            )
            
            # Update success message to show processing details
            refresh_status = " (with refresh)" if refresh_supply_factors else " (new facilities only)"
            success_message = (
                f"Power generation completed{refresh_status}. "
                f"SAM processed {sam_processed_count} renewable facilities, "
                f"traditional model processed {traditional_processed_count} facilities"
            )
            
            if skipped_count > 0:
                success_message += f", skipped {skipped_count} facilities with existing data"
            
            success_message += "."
            
            logger.info(success_message)
            request.session['success_message'] = success_message
            
        except Exception as e:
            logger.error(f"Error in power generation: {e}")
            success_message = f"Error in power generation: {str(e)}"
            request.session['success_message'] = f"Error in power generation: {str(e)}"

    return redirect('powermapui_home')

def process_facilities(config, facilities_list, demand_year, scenario, refresh_supply_factors=False):
    """
    Process renewable facilities using SAM
    
    Args:
        refresh_supply_factors: If True, refresh supply factors for all facilities.
                              If False, only process facilities without existing supply factors.
    
    Returns:
        tuple: (sam_processed_count, traditional_processed_count, skipped_count)
    """
    
    # Initialize SAM processor
    weather_dir = getattr(settings, 'WEATHER_DATA_DIR', 'weather_data')
    power_curves_dir = getattr(settings, 'POWER_CURVES_DIR', 'power_curves')
    sam_processor = SAMResourceProcessor(
        config_settings=config,
        weather_data_dir=weather_dir,
        power_curves_dir=power_curves_dir
    )
    sam_processed_count, traditional_processed_count, skipped_count = 0, 0, 0
    
    for facility_data in facilities_list:
        try:
            facility_obj = facilities.objects.get(
                facility_code=facility_data.get('facility_code')
            )
            
            # Check if supply factors already exist for this facility/year
            existing_supply_factors = supplyfactors.objects.filter(
                idfacilities=facility_obj.idfacilities,
                year=demand_year
            ).exists()
            
            # Skip processing if supply factors exist and refresh is not requested
            if existing_supply_factors and not refresh_supply_factors:
                skipped_count += 1
                logger.debug(f"Skipped {facility_obj.facility_name} - supply factors already exist for {demand_year}")
                continue
            
            technology = facility_obj.idtechnologies
            tech_name = technology.technology_name.lower()
            
            # Process the facility
            if technology.renewable:
                results = process_renewable_facility(sam_processor, facility_obj, tech_name, demand_year)
                sam_processed_count += 1
            else:
                results = process_traditional_facility(facility_obj)
                traditional_processed_count += 1
                    
            if results:
                # Store supply factors (will overwrite existing if refresh_supply_factors=True)
                store_simulation_results(results, facility_obj, demand_year)
                
                if existing_supply_factors:
                    logger.info(f"Supply factors refreshed for {facility_obj.facility_name}")
                else:
                    logger.info(f"Supply factors created for new facility {facility_obj.facility_name}")

                # Always update facility summary values (capacity factor, generation)
                facility_obj.capacityfactor = results.capacity_factor
                facility_obj.generation = results.annual_energy
                facility_obj.save()
                
        except Exception as e:
            logger.error(f"Unexpected error processing facility {facility_data.get('facility_code')}: {e}")
            continue
    
    return sam_processed_count, traditional_processed_count, skipped_count

def process_renewable_facility(sam_processor, facility_obj, tech_name, demand_year):
    """
    Process renewable facilities using SAM
    
    Returns:
        int: Results of the SAM simulation or None if not applicable
    """
    processed_count = 0
    try:
        
        # ADD THIS DEBUG CODE TEMPORARILY
        # if tech_name in ['single axis pv', 'fixed pv', 'rooftop pv']:
        #     logger.info(f"=== DEBUGGING SOLAR FACILITY: {facility_obj.facility_name} ===")
        #     weather_data = sam_processor.debug_solar_weather_loading(facility_obj, tech_name, demand_year)
            
        #     if not weather_data or not weather_data.ghi:
        #         logger.error("No valid solar weather data found - cannot proceed with simulation")
        #         return None
            
        weather_file_path = sam_processor.get_weather_file_path(
            facility_obj.latitude, 
            facility_obj.longitude, 
            tech_name, 
            demand_year
        ) # type: ignore

        # # Debug the file format
        # sam_processor.debug_weather_file_format(weather_file_path, 15)
        
        # Load weather data
        weather_data = sam_processor.load_weather_data(weather_file_path)

        # Process based on technology type
        results = None

        if tech_name in ['onshore wind', 'offshore wind', 'offshore wind floating']:
            # Process wind facility
            power_curve = {}
            if facility_obj.turbine:
                power_curve_path = sam_processor.get_power_curve_file_path(
                    facility_obj.turbine
                )
                power_curve = sam_processor.load_power_curve(power_curve_path)
            
            results = sam_processor.process_wind_facility(
                facility_obj, demand_year, power_curve
            )
            
        elif tech_name in ['single axis pv', 'fixed pv', 'rooftop pv']:
            # Process solar facility
            results = sam_processor.process_solar_facility(
                facility_obj, weather_data
            )
            
            # Update facility with calculated values
            facility_obj.capacityfactor = results.capacity_factor
            facility_obj.generation = results.annual_energy
            facility_obj.save()
            
            processed_count += 1
                
    except WeatherFileError as e:
        logger.warning(f"Weather file issue for {facility_obj.facility_name}: {e}")
        pass
        
    except SAMError as e:
        logger.error(f"SAM simulation failed for {facility_obj.facility_name}: {e}")
        pass
    return results

def process_traditional_facility(facility_obj):
    """
    Process non-renewable facilities using traditional power model
    
    Returns:
        SimulationResults: Results object with constant generation
    """
    try:
        # Calculate constant generation (capacity in MW converted to kW)
        capacity_kw = facility_obj.capacity * facility_obj.capacityfactor * 1000  # Convert MW to kW
        
        # Create SimulationResults object with constant generation
        results = SimulationResults(
            annual_energy=capacity_kw * 8760,  # kWh/year (capacity × hours in year)
            hourly_generation=[capacity_kw] * 8760,  # Constant generation every hour
            capacity_factor=facility_obj.capacityfactor 
        )
        
        logger.debug(f"Traditional facility {facility_obj.facility_name}: "
                    f"{capacity_kw} kW capacity, {results.annual_energy:,.0f} kWh/year")
        
        return results
        
    except Exception as e:
        logger.error(f"Error in traditional power model for {facility_obj.facility_name}: {e}")
        return None

def store_simulation_results(results, facility_obj, demand_year):
    """
    Store SAM simulation results in the supplyfactors table
    
    Args:
        results: SimulationResults object
        facility_obj: Facility model instance
        technology: Technology model instance
        demand_year: Year being processed
        scenario: Scenario being processed
    """
    # Clear existing data for this facility/scenario/year
    supplyfactors.objects.filter(
        idfacilities=facility_obj.idfacilities,
        year=demand_year
    ).delete()
    
    # Create new records for each hour
    bulk_records = []
    for hour, generation in enumerate(results.hourly_generation):
        record = supplyfactors(
            idfacilities=facility_obj,
            year=demand_year,
            hour=hour,
            quantum=generation,
            supply=1  # Assuming supply=1 for generation
        )
        bulk_records.append(record)
    
    # Use bulk_create for better performance
    supplyfactors.objects.bulk_create(bulk_records, batch_size=1000)
    
