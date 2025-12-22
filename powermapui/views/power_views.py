from django.contrib.auth.decorators import login_required
from django.shortcuts import render
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

    # Get date range parameters
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

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

        # Only fetch the specific facility if in single facility mode
        if single_facility_mode and facility_code:
            try:
                facility_obj = facilities.objects.get(facility_code=facility_code)
                facilities_list = [{
                    'facility_code': facility_obj.facility_code,
                    'facility_name': facility_obj.facility_name,
                }]
            except facilities.DoesNotExist:
                raise Exception(f"Facility '{facility_code}' not found")
        else:
            facilities_list = fetch_full_facilities_data(demand_year, scenario)

        config = fetch_all_config_data(request)

        # Process facilities - pass single facility parameters and date range
        sam_processed_count, skipped_count = process_facilities(
            config,
            facilities_list,
            weather_year,
            scenario,
            refresh_supply_factors,
            single_facility_code=facility_code if single_facility_mode else None,
            start_date=start_date,
            end_date=end_date
        )
        
        # Update success message to show processing details
        if single_facility_mode:
            if sam_processed_count > 0:
                success_message = f"Successfully processed facility '{facility_code}'."

                # Add date range info if specified
                if start_date or end_date:
                    from datetime import datetime, timedelta
                    year = int(weather_year)
                    base_date = datetime(year, 1, 1, 0, 0, 0)

                    if start_date:
                        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
                        start_hour = int((start_dt - base_date).total_seconds() / 3600)
                    else:
                        start_hour = 0

                    if end_date:
                        end_dt = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1) - timedelta(hours=1)
                        end_hour = int((end_dt - base_date).total_seconds() / 3600)
                    else:
                        end_hour = 8759 if year % 4 != 0 else 8783  # Handle leap years

                    num_hours = end_hour - start_hour + 1
                    success_message += f" Stored {num_hours} hours (hour {start_hour} to {end_hour})."

                    if start_date and end_date:
                        success_message += f" Date range: {start_date} to {end_date}."
                    elif start_date:
                        success_message += f" From: {start_date}."
                    elif end_date:
                        success_message += f" Until: {end_date}."
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

        # Render the same page with success message instead of redirecting
        # Get list of renewable facilities for the dropdown (if needed again)
        renewable_facilities = []
        all_facilities = fetch_full_facilities_data(demand_year, scenario) or []
        for facility_data in all_facilities:
            try:
                facility_obj = facilities.objects.get(
                    facility_code=facility_data.get('facility_code')
                )
                technology = facility_obj.idtechnologies
                if technology and technology.renewable and not technology.dispatchable:
                    renewable_facilities.append({
                        'facility_code': facility_obj.facility_code,
                        'facility_name': facility_obj.facility_name,
                        'technology': technology.technology_name
                    })
            except facilities.DoesNotExist:
                continue

        context = {
            'weather_year': weather_year,
            'demand_year': demand_year,
            'scenario': scenario,
            'config_file': config_file,
            'renewable_facilities': renewable_facilities,
            'success_message': success_message,
        }
        return render(request, 'generate_power.html', context)

    except Exception as e:
        logger.error(f"Error in power generation: {e}")
        error_message = f"Error in power generation: {str(e)}"

        # Get list of renewable facilities for the dropdown
        renewable_facilities = []
        try:
            all_facilities = fetch_full_facilities_data(demand_year, scenario) or []
            for facility_data in all_facilities:
                try:
                    facility_obj = facilities.objects.get(
                        facility_code=facility_data.get('facility_code')
                    )
                    technology = facility_obj.idtechnologies
                    if technology and technology.renewable and not technology.dispatchable:
                        renewable_facilities.append({
                            'facility_code': facility_obj.facility_code,
                            'facility_name': facility_obj.facility_name,
                            'technology': technology.technology_name
                        })
                except facilities.DoesNotExist:
                    continue
        except:
            pass

        context = {
            'weather_year': weather_year,
            'demand_year': demand_year,
            'scenario': scenario,
            'config_file': config_file,
            'renewable_facilities': renewable_facilities,
            'error_message': error_message,
        }
        return render(request, 'generate_power.html', context)

def process_facilities(config, facilities_list, weather_year, scenario, refresh_supply_factors=False, single_facility_code=None, start_date=None, end_date=None):
    """
    Process renewable facilities using SAM

    Args:
        refresh_supply_factors: If True, refresh supply factors for all facilities.
                              If False, only process facilities without existing supply factors.
        single_facility_code: If provided, only process this specific facility (always refreshes)
        start_date: Optional start date (YYYY-MM-DD) to filter generation data
        end_date: Optional end date (YYYY-MM-DD) to filter generation data

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
                continue

            # Process hybrid facilities: handle multiple renewable technologies
            all_results = process_hybrid_facility(
                sam_processor, facility_obj, weather_year, start_date, end_date
            )

            if all_results:
                sam_processed_count += 1

                # Store combined supply factors (will overwrite existing if refresh_supply_factors=True)
                store_simulation_results(all_results, facility_obj, weather_year, start_date, end_date)

                # Always update facility summary values (capacity factor, generation)
                facility_obj.capacityfactor = all_results.capacity_factor
                facility_obj.save()

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

def process_hybrid_facility(sam_processor, facility_obj, weather_year, start_date=None, end_date=None):
    """
    Process a facility that may have multiple renewable technologies (hybrid).
    Handles wind, solar, and combinations of both.

    Args:
        sam_processor: SAMResourceProcessor instance
        facility_obj: Facility model instance
        weather_year: Year string for weather data
        start_date: Optional start date to filter results
        end_date: Optional end date to filter results

    Returns:
        SimulationResults: Combined results for all technologies at this facility
    """
    from siren_web.models import FacilitySolar, FacilityWindTurbines

    combined_hourly_generation = None
    total_annual_energy = 0
    total_capacity = 0
    technologies_processed = []

    # Process wind installations
    wind_installations = FacilityWindTurbines.objects.filter(
        idfacilities=facility_obj,
        is_active=True
    )

    for wind_install in wind_installations:
        try:
            technology = wind_install.idtechnologies
            if technology and technology.renewable and not technology.dispatchable:
                fuel_type = technology.fuel_type.lower()

                # Get power curve for this specific turbine
                power_curve = {}
                if wind_install.wind_turbine:
                    turbine = wind_install.wind_turbine
                    power_curve_path = sam_processor.get_power_curve_file_path(turbine.turbine_model)
                    power_curve = sam_processor.load_power_curve(power_curve_path)

                # Create a temporary facility-like object for this installation
                results = process_wind_installation(
                    sam_processor, facility_obj, wind_install, power_curve, weather_year
                )

                if results:
                    technologies_processed.append(f"Wind-{wind_install.wind_turbine.turbine_model if wind_install.wind_turbine else 'Unknown'}")
                    total_annual_energy += results.annual_energy
                    total_capacity += wind_install.total_capacity or 0

                    # Combine hourly generation
                    if combined_hourly_generation is None:
                        combined_hourly_generation = list(results.hourly_generation)
                    else:
                        for i in range(min(len(combined_hourly_generation), len(results.hourly_generation))):
                            combined_hourly_generation[i] += results.hourly_generation[i]

        except Exception as e:
            logger.error(f"Error processing wind installation at {facility_obj.facility_name}: {e}")
            continue

    # Process solar installations
    solar_installations = FacilitySolar.objects.filter(
        idfacilities=facility_obj,
        is_active=True
    )

    for solar_install in solar_installations:
        try:
            technology = solar_install.idtechnologies
            if technology and technology.renewable and not technology.dispatchable:

                results = process_solar_installation(
                    sam_processor, facility_obj, solar_install, weather_year
                )

                if results:
                    technologies_processed.append(f"Solar-{technology.technology_name}")
                    total_annual_energy += results.annual_energy
                    total_capacity += solar_install.nameplate_capacity or solar_install.ac_capacity or 0

                    # Combine hourly generation
                    if combined_hourly_generation is None:
                        combined_hourly_generation = list(results.hourly_generation)
                    else:
                        for i in range(min(len(combined_hourly_generation), len(results.hourly_generation))):
                            combined_hourly_generation[i] += results.hourly_generation[i]

        except Exception as e:
            logger.error(f"Error processing solar installation at {facility_obj.facility_name}: {e}")
            continue

    # Fallback to legacy single-technology processing if no installations found
    if not technologies_processed and facility_obj.idtechnologies:
        technology = facility_obj.idtechnologies
        fuel_type = technology.fuel_type.lower()

        if technology.renewable and not technology.dispatchable:
            results = process_renewable_facility(sam_processor, facility_obj, fuel_type, weather_year)
            if results:
                combined_hourly_generation = list(results.hourly_generation)
                total_annual_energy = results.annual_energy
                total_capacity = facility_obj.capacity or 0
                technologies_processed.append(technology.technology_name)

    if not technologies_processed:
        logger.warning(f"No renewable technologies found for {facility_obj.facility_name}")
        return None

    # Apply date filtering if requested
    if start_date or end_date:
        combined_hourly_generation = filter_hourly_data_by_date(
            combined_hourly_generation, weather_year, start_date, end_date
        )

    # Calculate combined capacity factor
    if total_capacity > 0:
        # Capacity factor = actual energy / (capacity * hours)
        hours_in_data = len(combined_hourly_generation)
        max_possible_energy = total_capacity * 1000 * hours_in_data  # Convert MW to kW
        capacity_factor = (sum(combined_hourly_generation) / max_possible_energy * 100) if max_possible_energy > 0 else 0
    else:
        capacity_factor = 0

    # Return combined results
    return SimulationResults(
        annual_energy=total_annual_energy,
        hourly_generation=combined_hourly_generation,
        capacity_factor=capacity_factor,
        additional_metrics={
            'technologies': technologies_processed,
            'total_capacity_mw': total_capacity
        }
    )

def process_wind_installation(sam_processor, facility_obj, wind_install, power_curve, weather_year):
    """
    Process a specific wind installation within a facility.
    """
    try:
        weather_file_path = sam_processor.get_weather_file_path(
            facility_obj.latitude,
            facility_obj.longitude,
            wind_install.idtechnologies.technology_name if wind_install.idtechnologies else 'wind',
            weather_year
        )

        if not weather_file_path:
            logger.warning(f"No weather file found for wind installation at {facility_obj.facility_name}")
            return None

        # Load weather data
        weather_data = sam_processor.load_weather_data(weather_file_path)

        # Process using the wind installation's specific parameters
        results = sam_processor.process_wind_facility(
            facility_obj, weather_year, power_curve, wind_install
        )

        return results

    except Exception as e:
        logger.error(f"Error processing wind installation: {e}")
        return None

def process_solar_installation(sam_processor, facility_obj, solar_install, weather_year):
    """
    Process a specific solar installation within a facility.
    """
    try:
        weather_file_path = sam_processor.get_weather_file_path(
            facility_obj.latitude,
            facility_obj.longitude,
            solar_install.idtechnologies.technology_name if solar_install.idtechnologies else 'solar',
            weather_year
        )

        if not weather_file_path:
            logger.warning(f"No weather file found for solar installation at {facility_obj.facility_name}")
            return None

        # Load weather data
        weather_data = sam_processor.load_weather_data(weather_file_path)

        # Create a temporary facility-like object with solar installation parameters
        # Process using solar-specific parameters from the installation
        results = sam_processor.process_solar_facility(facility_obj, weather_data)

        # Scale results by the installation's capacity vs facility's total capacity
        if solar_install.nameplate_capacity and facility_obj.capacity:
            scale_factor = solar_install.nameplate_capacity / facility_obj.capacity
            if scale_factor != 1.0:
                results.annual_energy *= scale_factor
                results.hourly_generation = [h * scale_factor for h in results.hourly_generation]

        return results

    except Exception as e:
        logger.error(f"Error processing solar installation: {e}")
        return None

def filter_hourly_data_by_date(hourly_data, weather_year, start_date=None, end_date=None):
    """
    Filter hourly generation data by date range.

    Args:
        hourly_data: List of hourly generation values
        weather_year: Year string
        start_date: Start date string (YYYY-MM-DD)
        end_date: End date string (YYYY-MM-DD)

    Returns:
        Filtered list of hourly values
    """
    from datetime import datetime, timedelta

    if not start_date and not end_date:
        return hourly_data

    try:
        year = int(weather_year)
        base_date = datetime(year, 1, 1, 0, 0, 0)

        # Parse dates
        if start_date:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        else:
            start_dt = base_date

        if end_date:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1) - timedelta(hours=1)
        else:
            end_dt = datetime(year, 12, 31, 23, 0, 0)

        # Calculate hour indices
        start_hour = int((start_dt - base_date).total_seconds() / 3600)
        end_hour = int((end_dt - base_date).total_seconds() / 3600)

        # Ensure indices are within bounds
        start_hour = max(0, min(start_hour, len(hourly_data) - 1))
        end_hour = max(0, min(end_hour + 1, len(hourly_data)))

        return hourly_data[start_hour:end_hour]

    except Exception as e:
        logger.error(f"Error filtering hourly data by date: {e}")
        return hourly_data

def process_renewable_facility(sam_processor, facility_obj, fuel_type, weather_year):
    """
    Process renewable facilities using SAM
    
    Returns:
        SimulationResults: Results of the SAM simulation or None if not applicable
    """
    try:
        weather_file_path = sam_processor.get_weather_file_path(
            facility_obj.latitude, 
            facility_obj.longitude, 
            fuel_type, 
            weather_year
        )
        
        # Load weather data
        weather_data = sam_processor.load_weather_data(weather_file_path)

        # Process based on technology type
        results = None

        if fuel_type == 'wind':
            # Process wind facility
            power_curve = {}
            
            # Get wind turbine info from related FacilityWindTurbines model
            wind_installation = facility_obj.facilitywindturbines_set.filter(is_active=True).first()
            
            if wind_installation:
                turbine = wind_installation.wind_turbine
                power_curve_path = sam_processor.get_power_curve_file_path(
                    turbine.turbine_model
                )
                power_curve = sam_processor.load_power_curve(power_curve_path)
            
            results = sam_processor.process_wind_facility(
                facility_obj, weather_year, power_curve, wind_installation
            )
            
        elif fuel_type == 'solar':
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

def store_simulation_results(results, facility_obj, weather_year, start_date=None, end_date=None):
    """
    Store SAM simulation results in the supplyfactors table

    Args:
        results: SimulationResults object
        facility_obj: Facility model instance
        weather_year: Year being processed
        start_date: Optional start date for filtering (YYYY-MM-DD)
        end_date: Optional end date for filtering (YYYY-MM-DD)
    """
    from datetime import datetime, timedelta

    # Clear existing data for this facility/year (or date range)
    if start_date or end_date:
        # Calculate hour range for deletion
        year = int(weather_year)
        base_date = datetime(year, 1, 1, 0, 0, 0)

        if start_date:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            start_hour = int((start_dt - base_date).total_seconds() / 3600)
        else:
            start_hour = 0

        if end_date:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1) - timedelta(hours=1)
            end_hour = int((end_dt - base_date).total_seconds() / 3600)
        else:
            end_hour = 8759

        # Delete only records in the specified date range
        supplyfactors.objects.filter(
            idfacilities=facility_obj.idfacilities,
            year=weather_year,
            hour__gte=start_hour,
            hour__lte=end_hour
        ).delete()
    else:
        # Clear all data for this facility/year
        supplyfactors.objects.filter(
            idfacilities=facility_obj.idfacilities,
            year=weather_year
        ).delete()

    # Calculate the starting hour offset based on date range
    if start_date:
        year = int(weather_year)
        base_date = datetime(year, 1, 1, 0, 0, 0)
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        hour_offset = int((start_dt - base_date).total_seconds() / 3600)
    else:
        hour_offset = 0

    # Create new records for each hour
    bulk_records = []
    for idx, generation in enumerate(results.hourly_generation):
        actual_hour = hour_offset + idx
        record = supplyfactors(
            idfacilities=facility_obj,
            year=weather_year,
            hour=actual_hour,
            quantum=generation,
            supply=1  # Assuming supply=1 for generation
        )
        bulk_records.append(record)

    # Use bulk_create for better performance
    supplyfactors.objects.bulk_create(bulk_records, batch_size=1000)
