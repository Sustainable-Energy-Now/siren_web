from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect
from django.conf import settings
from common.decorators import settings_required
import logging
import numpy as np

from siren_web.database_operations import (
    fetch_full_facilities_data,
    fetch_module_settings_data,
    fetch_scenario_settings_data,
    resolve_demand_override,
    get_demand_scenario_context,
)
from siren_web.models import facilities, Scenarios, Technologies
from siren_web.services.supply_matrix import set_facility_trace, clear_facility_trace, facility_has_trace
from siren_web.services.biomass_trace_from_scada import MIN_COVERAGE_DEFAULT as BIOMASS_MIN_COVERAGE_DEFAULT

# Import the SAM processor
from powermapui.views.sam_resource_processor import SAMResourceProcessor, SAMError, WeatherFileError, SimulationResults
from powermapui.utils.representative_turbine import (
    NoRepresentativeTurbine, resolve_wind_facility, resolve_wind_installation,
)
from powermapui.utils.turbine_library import TurbineLibraryError

logger = logging.getLogger(__name__)

@login_required
@settings_required(redirect_view='powermapui:powermapui_home', require_demand_year=False)
def generate_power(request):
    """
    Generate power for all facilities using SAM for renewables
    """
    scenario = request.session.get('scenario', '')
    config_file = request.session.get('config_file')
    # Both the year TechnologyYears data is read for (via
    # fetch_full_facilities_data) and the weather year SAM simulates against
    # come from whichever Demand forecast is selected on this page's own
    # Demand Forecast selector (see get_demand_scenario_context /
    # resolve_demand_override) -- carried on every request as the
    # demand_scenario_demand query param, never from the session.
    demand_id = request.GET.get('demand_scenario_demand')
    demand_override = resolve_demand_override(demand_id)
    demand_year = demand_override.year if demand_override else None

    # The weather year SAM simulates against: the reference_year of the
    # selected Demand forecast (the real FacilityScada year its own trace's
    # shape was synthesised from -- see Demand.reference_year /
    # esoo_scenario_views.build_scenario_from_esoo), so generation and
    # demand are chronologically consistent. A legacy forecast built before
    # reference_year existed has none recorded.
    weather_year = str(demand_override.reference_year) if demand_override and demand_override.reference_year else None

    # Check if this is just displaying the confirmation page
    if request.method == 'GET' and not request.GET.get('confirm'):
        # Get list of renewable facilities for the dropdown -- only once a
        # Demand Forecast is selected, since it supplies the year
        # fetch_full_facilities_data reads TechnologyYears for.
        renewable_facilities = []
        if demand_year is not None:
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

        if demand_override is not None and not demand_override.reference_year:
            messages.error(
                request,
                f"The selected Demand forecast '{demand_override.demand_name}' has no reference "
                "year recorded, so a weather year for SAM can't be determined."
            )

        # Show the confirmation template first
        context = {
            'weather_year': weather_year,
            'demand_year': demand_year,
            'scenario': scenario,
            'config_file': config_file,
            'renewable_facilities': renewable_facilities,
            'biomass_min_coverage_default': BIOMASS_MIN_COVERAGE_DEFAULT,
            **get_demand_scenario_context(demand_id),
        }
        return render(request, 'generate_power.html', context)

    # Every run action (confirm=true) needs a fully-resolved Demand Forecast
    # -- send the user back to the selector above rather than the map home,
    # since that's where the fix is.
    if demand_override is None:
        messages.error(
            request,
            "Select a Demand Forecast before running -- it supplies both the year to run "
            "against and the weather year SAM simulates against."
        )
        return redirect('powermapui:generate_power')
    if not demand_override.reference_year:
        messages.error(
            request,
            f"The selected Demand forecast '{demand_override.demand_name}' has no reference "
            "year recorded, so a weather year for SAM can't be determined."
        )
        return redirect('powermapui:generate_power')

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

    # Biomass has no SAM weather-file input -- its trace is built from real
    # FacilityScadaMatrix history instead (see process_biomass_facility),
    # gated on this minimum fraction of non-missing half-hourly intervals
    # per year. Same default and validation range as the
    # build_biomass_supply_traces/split_biomass_dispatch management commands.
    raw_min_coverage = request.POST.get('biomass_min_coverage') or request.GET.get('biomass_min_coverage')
    try:
        biomass_min_coverage = float(raw_min_coverage) if raw_min_coverage else BIOMASS_MIN_COVERAGE_DEFAULT
        if not (0 < biomass_min_coverage <= 1):
            raise ValueError
    except (TypeError, ValueError):
        biomass_min_coverage = BIOMASS_MIN_COVERAGE_DEFAULT

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

        # Process facilities - pass single facility parameters and date range
        sam_processed_count, skipped_count, skip_reason = process_facilities(
            facilities_list,
            weather_year,
            scenario,
            refresh_supply_factors,
            single_facility_code=facility_code if single_facility_mode else None,
            start_date=start_date,
            end_date=end_date,
            biomass_min_coverage=biomass_min_coverage,
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
            elif skip_reason:
                # facility_obj was found (facilities.DoesNotExist would have
                # raised above) -- it just couldn't be processed, e.g.
                # insufficient SCADA coverage for a Biomass facility/year.
                success_message = f"'{facility_code}' was not processed: {skip_reason}"
            else:
                success_message = (
                    f"'{facility_code}' was not processed -- it isn't a renewable, "
                    "non-dispatchable technology (nothing for Run Power to build a trace for)."
                )
        else:
            refresh_status = " (with refresh)" if refresh_supply_factors else " (new facilities only)"
            success_message = (
                f"Power generation completed{refresh_status}. "
                f"SAM processed {sam_processed_count} renewable facilities."
            )

            if skipped_count > 0:
                success_message += f", skipped {skipped_count} facilities with existing data"

            success_message += f". Biomass coverage threshold: {biomass_min_coverage:.0%}."

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
            'biomass_min_coverage_default': biomass_min_coverage,
            **get_demand_scenario_context(demand_id),
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
            'biomass_min_coverage_default': biomass_min_coverage,
            **get_demand_scenario_context(demand_id),
        }
        return render(request, 'generate_power.html', context)

def process_facilities(facilities_list, weather_year, scenario, refresh_supply_factors=False, single_facility_code=None, start_date=None, end_date=None, biomass_min_coverage=BIOMASS_MIN_COVERAGE_DEFAULT):
    """
    Process renewable facilities using SAM

    Args:
        refresh_supply_factors: If True, refresh supply factors for all facilities.
                              If False, only process facilities without existing supply factors.
        single_facility_code: If provided, only process this specific facility (always refreshes)
        start_date: Optional start date (YYYY-MM-DD) to filter generation data
        end_date: Optional end date (YYYY-MM-DD) to filter generation data
        biomass_min_coverage: Minimum fraction (0-1) of non-missing half-hourly
                              SCADA intervals required to build a Biomass trace
                              for a facility/year -- see process_biomass_facility.

    Returns:
        tuple: (sam_processed_count, skipped_count, skip_reason). skip_reason
        is only ever populated when single_facility_code was given and that
        one facility produced no results (see process_biomass_facility) --
        None in every other case, including the batch/all-facilities mode.
    """

    # Initialize SAM processor
    weather_dir = getattr(settings, 'WEATHER_DATA_DIR', 'weather_data')
    sam_processor = SAMResourceProcessor(weather_data_dir=weather_dir)
    sam_processed_count, skipped_count = 0, 0
    skip_reason = None

    for facility_data in facilities_list:
        try:
            facility_obj = facilities.objects.get(
                facility_code=facility_data.get('facility_code')
            )

            # If single facility mode, skip all other facilities
            if single_facility_code and facility_obj.facility_code != single_facility_code:
                continue

            # Check if supply factors already exist for this facility/year
            existing_supply_factors = facility_has_trace(int(weather_year), facility_obj.idfacilities)

            # Skip processing if supply factors exist and refresh is not requested
            if existing_supply_factors and not refresh_supply_factors:
                skipped_count += 1
                continue

            # Process hybrid facilities: handle multiple renewable technologies
            all_results, facility_skip_reason = process_hybrid_facility(
                sam_processor, facility_obj, weather_year, start_date, end_date,
                biomass_min_coverage=biomass_min_coverage,
            )

            if all_results:
                sam_processed_count += 1

                # Store combined supply factors (will overwrite existing if refresh_supply_factors=True)
                store_simulation_results(all_results, facility_obj, weather_year, start_date, end_date)

                # Always update facility summary values (capacity factor, generation)
                facility_obj.capacityfactor = all_results.capacity_factor
                facility_obj.save()
            elif single_facility_code and facility_obj.facility_code == single_facility_code:
                skip_reason = facility_skip_reason

            # If in single facility mode, stop after processing the target facility
            if single_facility_code and facility_obj.facility_code == single_facility_code:
                break

        except facilities.DoesNotExist:
            logger.error(f"Facility not found: {facility_data.get('facility_code')}")
            continue
        except Exception as e:
            logger.error(f"Unexpected error processing facility {facility_data.get('facility_code')}: {e}")
            continue

    return sam_processed_count, skipped_count, skip_reason

def process_hybrid_facility(sam_processor, facility_obj, weather_year, start_date=None, end_date=None, biomass_min_coverage=BIOMASS_MIN_COVERAGE_DEFAULT):
    """
    Process a facility that may have multiple renewable technologies (hybrid).
    Handles wind, solar, and combinations of both.

    Args:
        sam_processor: SAMResourceProcessor instance
        facility_obj: Facility model instance
        weather_year: Year string for weather data
        start_date: Optional start date to filter results
        end_date: Optional end date to filter results
        biomass_min_coverage: see process_facilities

    Returns:
        (SimulationResults, None) -- combined results for all technologies
        at this facility -- or (None, reason) if nothing could be built;
        reason is only ever populated by the Biomass path today (see
        process_biomass_facility), None for every other skip/failure.
    """
    from siren_web.models import FacilitySolar, FacilityWindTurbines

    combined_hourly_generation = None
    total_annual_energy = 0
    total_capacity = 0
    technologies_processed = []
    skip_reason = None
    assumed_turbines = []

    # Process wind installations
    wind_installations = FacilityWindTurbines.objects.filter(
        idfacilities=facility_obj,
        is_active=True
    )

    for wind_install in wind_installations:
        try:
            technology = wind_technology_for(wind_install, facility_obj)
            if technology and technology.renewable and not technology.dispatchable:
                fuel_type = (technology.fuel_type or 'WIND').lower()

                # The installation's own turbine curve, or -- when no turbine
                # model is specified -- a representative turbine sized to it
                turbine = resolve_wind_installation(wind_install)

                # Process this wind installation
                results = process_wind_installation(
                    sam_processor, facility_obj, turbine, weather_year, fuel_type
                )

                if results:
                    technologies_processed.append(f"Wind-{turbine.name}")
                    total_annual_energy += results.annual_energy
                    if turbine.kind == 'assumed':
                        # The farm is n copies of the scaled curve, so this is exactly the nameplate
                        total_capacity += turbine.installation_capacity_mw
                        assumed_turbines.append(turbine.basis)
                    else:
                        total_capacity += wind_install.total_capacity or turbine.installation_capacity_mw

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
                    sam_processor, facility_obj, solar_install, weather_year,
                    technology.fuel_type.lower()
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

        if technology.renewable and not technology.dispatchable:
            fuel_type = (technology.fuel_type or '').lower()
            # Biomass has no SAM weather-file input (see
            # SAMResourceProcessor.get_weather_file_path) -- build its trace
            # from real FacilityScadaMatrix history instead.
            if fuel_type == 'biomass':
                results, skip_reason = process_biomass_facility(
                    facility_obj, weather_year, min_coverage=biomass_min_coverage
                )
            else:
                results = process_renewable_facility(sam_processor, facility_obj, fuel_type, weather_year)
            if results:
                combined_hourly_generation = list(results.hourly_generation)
                total_annual_energy = results.annual_energy
                total_capacity = facility_obj.capacity or 0
                technologies_processed.append(technology.technology_name)

    if not technologies_processed:
        # Non-renewable and dispatchable technologies aren't simulated by SAM --
        # Powermatch uses their nameplate capacity (x capacity factor) instead --
        # so having nothing to process is expected, not a warning. Biomass
        # logs its own specific coverage warning in process_biomass_facility,
        # so it's excluded here too rather than adding a second, generic one.
        technology = facility_obj.idtechnologies
        if technology and (
            not technology.renewable
            or technology.dispatchable
            or (technology.fuel_type or '').lower() == 'biomass'
        ):
            pass  # No SAM processing needed/possible for this technology
        else:
            logger.warning(f"No renewable technologies found for {facility_obj.facility_name}")
        return None, skip_reason

    # Apply date filtering if requested
    if start_date or end_date:
        combined_hourly_generation = filter_hourly_data_by_date(
            combined_hourly_generation, weather_year, start_date, end_date
        )

    # Calculate combined capacity factor
    if total_capacity > 0:
        # Capacity factor = actual energy / (capacity * hours). NaN-aware --
        # a Biomass trace can carry NaN for genuinely missing intervals (see
        # process_biomass_facility); plain sum() would turn one NaN into a
        # NaN capacity_factor for the whole facility.
        hours_in_data = len(combined_hourly_generation)
        max_possible_energy = total_capacity * 1000 * hours_in_data  # Convert MW to kW
        actual_energy = float(np.nansum(combined_hourly_generation))
        capacity_factor = (actual_energy / max_possible_energy * 100) if max_possible_energy > 0 else 0
    else:
        capacity_factor = 0

    # Return combined results
    return SimulationResults(
        annual_energy=total_annual_energy,
        hourly_generation=combined_hourly_generation,
        capacity_factor=capacity_factor,
        additional_metrics={
            'technologies': technologies_processed,
            'total_capacity_mw': total_capacity,
            'assumed_turbines': assumed_turbines,
        }
    ), None

def wind_technology_for(wind_install, facility_obj):
    """
    Technology of a wind installation. Installations created as "Unspecified"
    have none, so fall back to the facility's wind technology, then to plain
    Onshore Wind.
    """
    technology = wind_install.idtechnologies
    if technology is None:
        facility_technology = facility_obj.idtechnologies
        if facility_technology is not None and facility_technology.category == 'Wind':
            technology = facility_technology
    if technology is None:
        technology = Technologies.objects.filter(
            category='Wind', technology_name__iexact='Onshore Wind'
        ).first()
    return technology

def process_wind_installation(sam_processor, facility_obj, turbine, weather_year, fuel_type):
    """
    Process a specific wind installation within a facility.

    Args:
        turbine: ResolvedTurbine for the installation
            (see powermapui.utils.representative_turbine.resolve_wind_installation)
    """
    try:
        weather_file_path = sam_processor.get_weather_file_path(
            facility_obj.latitude,
            facility_obj.longitude,
            fuel_type,
            weather_year
        )

        if not weather_file_path:
            logger.warning(f"No weather file found for wind installation at {facility_obj.facility_name}")
            return None

        # Load weather data
        weather_data = sam_processor.load_weather_data(weather_file_path)

        # Process using the resolved turbine's curve, dimensions and count
        results = sam_processor.process_wind_facility(
            facility_obj, weather_year, weather_data, turbine
        )

        return results

    except Exception as e:
        logger.error(f"Error processing wind installation: {e}")
        return None

def process_solar_installation(sam_processor, facility_obj, solar_install, weather_year, fuel_type):
    """
    Process a specific solar installation within a facility.
    """
    try:
        weather_file_path = sam_processor.get_weather_file_path(
            facility_obj.latitude,
            facility_obj.longitude,
            fuel_type,
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
            # Use the facility's active wind installation; with none, size a
            # representative farm from the facility's capacity
            wind_installation = facility_obj.facilitywindturbines_set.filter(is_active=True).first()
            turbine = (resolve_wind_installation(wind_installation) if wind_installation
                       else resolve_wind_facility(facility_obj))

            results = sam_processor.process_wind_facility(
                facility_obj, weather_year, weather_data, turbine
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

    except (NoRepresentativeTurbine, TurbineLibraryError) as e:
        logger.error(f"No usable wind turbine for {facility_obj.facility_name}: {e}")
        return None

def process_biomass_facility(facility_obj, weather_year, min_coverage=BIOMASS_MIN_COVERAGE_DEFAULT):
    """
    Build a Biomass facility's trace from its own FacilityScadaMatrix history
    instead of SAM -- biomass has no weather-file input for SAM to simulate
    against (see SAMResourceProcessor.get_weather_file_path), so plugging it
    into process_renewable_facility would only ever fail. Uses the same
    coverage-gated logic (siren_web.services.biomass_trace_from_scada) as the
    build_biomass_supply_traces/split_biomass_dispatch management commands,
    so Run Power and the dedicated pipeline commands agree on what counts as
    "enough real data" for a given facility/year, and produce the same trace
    when min_coverage matches (it defaults to the same value, but can be
    overridden here independently of those commands -- see generate_power's
    biomass_min_coverage form field).

    Returns:
        (SimulationResults, None) on the same hourly-kW/Perth-local-year
        convention SAM's own results use (so store_simulation_results and
        the surrounding hybrid-facility combining logic need no
        special-casing), or (None, reason) if this facility/year doesn't
        clear min_coverage -- reason is a user-safe message explaining why,
        for surfacing in the UI rather than only the log.
    """
    from siren_web.services.biomass_trace_from_scada import build_hourly_kw_trace, coverage_for_year

    year = int(weather_year)
    coverage = coverage_for_year(facility_obj.idfacilities, year)
    if coverage < min_coverage:
        reason = (
            f"Insufficient SCADA coverage for {year} ({coverage:.1%} < "
            f"{min_coverage:.1%} required) -- can't build a real Biomass trace."
        )
        logger.warning(f"{facility_obj.facility_name}: {reason}")
        return None, reason

    trace, dropped_leap_day = build_hourly_kw_trace(facility_obj.idfacilities, year)
    if dropped_leap_day:
        logger.info(f"{facility_obj.facility_name} {year}: dropped 29 Feb to keep the trace at 8760 hours.")

    # Keep NaN for genuinely missing intervals rather than 0-filling --
    # matches exactly what build_biomass_supply_traces stores, and NaN is
    # what set_facility_trace/the dispatch engine's np.nansum already expect
    # for "no data" (as opposed to a confirmed zero). process_hybrid_facility's
    # own capacity-factor recompute uses a NaN-aware sum for this reason.
    valid = ~np.isnan(trace)
    hourly_generation = trace.tolist()
    annual_energy = float(np.nansum(trace))  # each hourly kW value is also that hour's kWh
    nameplate_kw = (facility_obj.capacity or 0) * 1000
    valid_hours = int(valid.sum())
    capacity_factor = (
        annual_energy / (nameplate_kw * valid_hours) * 100
        if nameplate_kw and valid_hours else 0
    )

    return SimulationResults(
        annual_energy=annual_energy,
        hourly_generation=hourly_generation,
        capacity_factor=capacity_factor,
        additional_metrics={'technologies': ['Biomass (from SCADA)'], 'coverage': coverage},
    ), None

def store_simulation_results(results, facility_obj, weather_year, start_date=None, end_date=None):
    """
    Store SAM simulation results in the SupplyFactorMatrix.

    Args:
        results: SimulationResults object
        facility_obj: Facility model instance
        weather_year: Year being processed
        start_date: Optional start date for filtering (YYYY-MM-DD)
        end_date: Optional end date for filtering (YYYY-MM-DD)
    """
    from datetime import datetime, timedelta

    year = int(weather_year)

    # Clear existing data for this facility/year (or date range) before
    # writing the new trace, so a regenerated trace shorter than what it
    # replaces doesn't leave stale tail values behind.
    if start_date or end_date:
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

        clear_facility_trace(year, facility_obj.idfacilities, start_hour, end_hour)
        hour_offset = start_hour
    else:
        clear_facility_trace(year, facility_obj.idfacilities)
        hour_offset = 0

    set_facility_trace(
        year,
        facility_obj.idfacilities,
        list(results.hourly_generation),
        start_hour=hour_offset,
    )
