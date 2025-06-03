from django.contrib.auth.decorators import login_required
from django.shortcuts import render
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
from powermapui.views.sam_resource_processor import SAMResourceProcessor, SAMError, WeatherFileFinder, WeatherFileError

logger = logging.getLogger(__name__)

@login_required
def generate_power(request):
    """
    Generate power for all facilities using SAM for renewables and traditional models for others
    """
    demand_year = request.session.get('demand_year', '')
    scenario = request.session.get('scenario', '')
    config_file = request.session.get('config_file')
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
            
            # Initialize SAM processor
            weather_dir = getattr(settings, 'WEATHER_DATA_DIR', 'weather_data')
            power_curves_dir = getattr(settings, 'POWER_CURVES_DIR', 'power_curves')
            
            sam_processor = SAMResourceProcessor(
                config_settings=config,
                weather_data_dir=weather_dir,
                power_curves_dir=power_curves_dir
            )
            
            # Process renewable facilities with SAM
            sam_processed_count = process_renewable_facilities(
                sam_processor, facilities_list, demand_year, scenario
            )
            
            # Process non-renewable facilities with traditional model
            traditional_processed_count = process_traditional_facilities(
                config, facilities_list, demand_year, scenario, scenario_settings
            )
            
            success_message = (
                f"Power generation completed. "
                f"SAM processed {sam_processed_count} renewable facilities, "
                f"traditional model processed {traditional_processed_count} facilities."
            )
            
            logger.info(success_message)
            
        except Exception as e:
            logger.error(f"Error in power generation: {e}")
            success_message = f"Error in power generation: {str(e)}"
    
    context = {
        'demand_year': demand_year,
        'scenario': scenario,
        'config_file': config_file,
        'success_message': success_message,
    }
    
    return render(request, 'powermapui_home.html', context)

def process_renewable_facilities(sam_processor, facilities_list, demand_year, scenario):
    """
    Process renewable facilities using SAM
    
    Returns:
        int: Number of facilities processed
    """
    processed_count = 0
    
    for facility_data in facilities_list:
        try:
            facility_obj = facilities.objects.get(
                facility_code=facility_data.get('facility_code')
            )
            technology = facility_obj.idtechnologies
            
            # Only process renewable technologies with SAM
            if not technology.renewable:
                continue
            
            # Get weather file path
            tech_name = technology.technology_name.lower()
            weather_file_path = sam_processor.get_weather_file_path(
                facility_obj.latitude, 
                facility_obj.longitude, 
                tech_name, 
                demand_year
            ) # type: ignore
            
            try:
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
                        facility_obj, None
                    )
                    
                if results:
                    # Store results in supplyfactors table
                    store_simulation_results(
                        results, facility_obj, technology, demand_year, scenario
                    )
                    
                    # Update facility with calculated values
                    facility_obj.capacityfactor = results.capacity_factor
                    facility_obj.generation = results.annual_energy
                    facility_obj.save()
                    
                    processed_count += 1
                    
            except WeatherFileError as e:
                logger.warning(f"Weather file issue for {facility_obj.facility_name}: {e}")
                continue
                
            except SAMError as e:
                logger.error(f"SAM simulation failed for {facility_obj.facility_name}: {e}")
                continue
                
        except facilities.DoesNotExist:
            logger.warning(f"Facility not found: {facility_data.get('facility_code')}")
            continue
            
        except Exception as e:
            logger.error(f"Unexpected error processing facility {facility_data.get('facility_code')}: {e}")
            continue
    
    return processed_count

def process_traditional_facilities(config, facilities_list, demand_year, scenario, scenario_settings):
    """
    Process non-renewable facilities using traditional power model
    
    Returns:
        int: Number of facilities processed
    """
    processed_count = 0
    
    try:
        # Use original power model for non-renewable technologies
        scene = WAScene(config, facilities_list)
        power = PowerModel(config, scene._stations.stations, demand_year, scenario_settings)
        generated = power.getValues()
        
        # Store traditional power model results
        for station in power.stations:
            try:
                if power.ly.get(station.name):
                    facility_obj = facilities.objects.get(facility_code=station.name)
                    technology = facility_obj.idtechnologies
                    
                    # Only use traditional model for non-renewable technologies
                    if not technology.renewable:
                        for hour, generation in enumerate(power.ly[station.name]):
                            supplyfactors.objects.update_or_create(
                                idscenarios_id=scenario,
                                idtechnologies=technology,
                                idzones=facility_obj.idzones,
                                year=demand_year,
                                hour=hour,
                                defaults={
                                    'quantum': generation,
                                    'supply': 1
                                }
                            )
                        processed_count += 1
                        
            except facilities.DoesNotExist:
                logger.warning(f"Facility not found for traditional processing: {station.name}")
                continue
                
            except Exception as e:
                logger.error(f"Error with traditional model for {station.name}: {e}")
                continue
                
    except Exception as e:
        logger.error(f"Error in traditional power model: {e}")
    
    return processed_count

def store_simulation_results(results, facility_obj, technology, demand_year, scenario):
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
    scenario_obj = Scenarios.objects.get(title=scenario)
    supplyfactors.objects.filter(
        idscenarios_id=scenario_obj.idscenarios,
        idtechnologies=technology,
        idzones=facility_obj.idzones,
        year=demand_year
    ).delete()
    
    # Create new records for each hour
    bulk_records = []
    for hour, generation in enumerate(results.hourly_generation):
        record = supplyfactors(
            idscenarios_id=scenario_obj.idscenarios,
            idtechnologies=technology,
            idzones=facility_obj.idzones,
            year=demand_year,
            hour=hour,
            quantum=generation,
            supply=1  # Assuming supply=1 for generation
        )
        bulk_records.append(record)
    
    # Use bulk_create for better performance
    supplyfactors.objects.bulk_create(bulk_records, batch_size=1000)
    