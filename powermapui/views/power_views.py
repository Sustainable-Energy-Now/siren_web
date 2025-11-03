from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.conf import settings
from common.decorators import settings_required
import logging

from siren_web.database_operations import (
    fetch_full_facilities_data, 
    fetch_module_settings_data, 
    fetch_scenario_settings_data, 
    fetch_all_config_data
)
from siren_web.models import facilities, supplyfactors, Scenarios

# Import the SAM processor
from powermapui.views.sam_resource_processor import SAMResourceProcessor, SAMError, WeatherFileError, SimulationResults

logger = logging.getLogger(__name__)

@login_required
@settings_required(redirect_view='powermapui:powermapui_home')
def generate_power(request):
    """
    Generate power for all facilities using SAM for renewables
    """
    weather_year = request.session.get('weather_year', '')
    demand_year = request.session.get('demand_year', '')
    scenario = request.session.get('scenario', '')
    config_file = request.session.get('config_file')
    
    # Check if this is just displaying the confirmation page
    if request.method == 'GET' and not request.GET.get('confirm'):
        # Get list of renewable facilities for the dropdown
        renewable_facilities = []
        facilities_list = fetch_full_facilities_data(demand_year, scenario)
        for facility_data in facilities_list:
            try:
                facility_obj = facilities.objects.get(
                    facility_code=facility_data.get('facility_code')
                )
                technology = facility_obj.idtechnologies
                if technology.renewable and not technology.dispatchable:
                    renewable_facilities.append({
                        'facility_code': facility_obj.facility_code,
                        'facility_name': facility_obj.facility_name,
                        'technology': technology.technology_name
                    })
            except facilities.DoesNotExist:
                continue
        
        # Show the confirmation template first
        context = {
            'weather_year': weather_year,
            'demand_year': demand_year,
            'scenario': scenario,
            'config_file': config_file,
            'renewable_facilities': renewable_facilities,
        }
        return render(request, 'generate_power.html', context)
    
    # Check if this is a single facility run
    single_facility_mode = request.GET.get('single_facility') == 'true'
    facility_code = request.GET.get('facility_code')
    
    # Add refresh parameter - can come from POST or GET with confirm
    refresh_supply_factors = (
        request.POST.get('refresh_supply_factors') == 'true' or 
        request.GET.get('refresh_supply_factors') == 'true'
    )
    
    # For single facility mode, always refresh
    if single_facility_mode:
        refresh_supply_factors = True
    
    success_message = ""
    
    try:
        # Get configuration and settings
        scenario_settings = fetch_module_settings_data('Powermap')
        if not scenario_settings:
            scenario_settings = fetch_scenario_settings_data(scenario)
            
        facilities_list = fetch_full_facilities_data(demand_year, scenario)
        config = fetch_all_config_data(request)
        
        # Process facilities - pass single facility parameters
        sam_processed_count, skipped_count = process_facilities(
            config, 
            facilities_list, 
            weather_year, 
            scenario, 
            refresh_supply_factors,
            single_facility_code=facility_code if single_facility_mode else None
        )
        
        # Update success message to show processing details
        if single_facility_mode:
            if sam_processed_count > 0:
                success_message = f"Successfully processed facility '{facility_code}'."
            else:
                success_message = f"No renewable facility found with code '{facility_code}'."
        else:
            refresh_status = " (with refresh)" if refresh_supply_factors else " (new facilities only)"
            success_message = (
                f"Power generation completed{refresh_status}. "
                f"SAM processed {sam_processed_count} renewable facilities."
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

    return redirect('powermapui:powermapui_home')

def process_facilities(config, facilities_list, weather_year, scenario, refresh_supply_factors=False, single_facility_code=None):
    """
    Process renewable facilities using SAM
    
    Args:
        refresh_supply_factors: If True, refresh supply factors for all facilities.
                              If False, only process facilities without existing supply factors.
        single_facility_code: If provided, only process this specific facility (always refreshes)
    
    Returns:
        tuple: (sam_processed_count, skipped_count)
    """
    
    # Initialize SAM processor
    weather_dir = getattr(settings, 'WEATHER_DATA_DIR', 'weather_data')
    power_curves_dir = getattr(settings, 'POWER_CURVES_DIR', 'power_curves')
    sam_processor = SAMResourceProcessor(
        config_settings=config,
        weather_data_dir=weather_dir,
        power_curves_dir=power_curves_dir
    )
    sam_processed_count, skipped_count = 0, 0
    
    for facility_data in facilities_list:
        try:
            facility_obj = facilities.objects.get(
                facility_code=facility_data.get('facility_code')
            )
            
            # If single facility mode, skip all other facilities
            if single_facility_code and facility_obj.facility_code != single_facility_code:
                continue
            
            # Check if supply factors already exist for this facility/year
            existing_supply_factors = supplyfactors.objects.filter(
                idfacilities=facility_obj.idfacilities,
                year=weather_year
            ).exists()
            
            # Skip processing if supply factors exist and refresh is not requested
            if existing_supply_factors and not refresh_supply_factors:
                skipped_count += 1
                logger.debug(f"Skipped {facility_obj.facility_name} - supply factors already exist for {weather_year}")
                continue
            
            technology = facility_obj.idtechnologies
            tech_name = technology.technology_name.lower()
            
            # Process the facility
            if technology.renewable and not technology.dispatchable:
                results = process_renewable_facility(sam_processor, facility_obj, tech_name, weather_year)
                
                if results:
                    sam_processed_count += 1
                    # Store supply factors (will overwrite existing if refresh_supply_factors=True)
                    store_simulation_results(results, facility_obj, weather_year)
                    
                    if existing_supply_factors:
                        logger.info(f"Supply factors refreshed for {facility_obj.facility_name}")
                    else:
                        logger.info(f"Supply factors created for new facility {facility_obj.facility_name}")

                    # Always update facility summary values (capacity factor, generation)
                    facility_obj.capacityfactor = results.capacity_factor
                    facility_obj.generation = results.annual_energy
                    facility_obj.save()
            else:
                continue  # Skip non-renewable facilities for SAM processing
            
            # If in single facility mode, stop after processing the target facility
            if single_facility_code and facility_obj.facility_code == single_facility_code:
                break
                
        except facilities.DoesNotExist:
            logger.error(f"Facility not found: {facility_data.get('facility_code')}")
            continue
        except Exception as e:
            logger.error(f"Unexpected error processing facility {facility_data.get('facility_code')}: {e}")
            continue
    
    return sam_processed_count, skipped_count

def process_renewable_facility(sam_processor, facility_obj, tech_name, weather_year):
    """
    Process renewable facilities using SAM
    
    Returns:
        SimulationResults: Results of the SAM simulation or None if not applicable
    """
    try:
        weather_file_path = sam_processor.get_weather_file_path(
            facility_obj.latitude, 
            facility_obj.longitude, 
            tech_name, 
            weather_year
        )
        
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
                facility_obj, weather_year, power_curve
            )
            
        elif tech_name in ['single axis pv', 'fixed pv', 'rooftop pv']:
            # Process solar facility
            results = sam_processor.process_solar_facility(
                facility_obj, weather_data
            )
            
        return results
                
    except WeatherFileError as e:
        logger.warning(f"Weather file issue for {facility_obj.facility_name}: {e}")
        return None
        
    except SAMError as e:
        logger.error(f"SAM simulation failed for {facility_obj.facility_name}: {e}")
        return None

def store_simulation_results(results, facility_obj, weather_year):
    """
    Store SAM simulation results in the supplyfactors table
    
    Args:
        results: SimulationResults object
        facility_obj: Facility model instance
        weather_year: Year being processed
    """
    # Clear existing data for this facility/year
    supplyfactors.objects.filter(
        idfacilities=facility_obj.idfacilities,
        year=weather_year
    ).delete()
    
    # Create new records for each hour
    bulk_records = []
    for hour, generation in enumerate(results.hourly_generation):
        record = supplyfactors(
            idfacilities=facility_obj,
            year=weather_year,
            hour=hour,
            quantum=generation,
            supply=1  # Assuming supply=1 for generation
        )
        bulk_records.append(record)
    
    # Use bulk_create for better performance
    supplyfactors.objects.bulk_create(bulk_records, batch_size=1000)