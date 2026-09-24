# database operations
from dataclasses import dataclass
from django.db import connection
from django.db.models import Prefetch
import logging
from django.db.models import Avg, Q, F, Sum, Count, When, OuterRef, Subquery
from django.db.models.functions import TruncDay
import os
import numpy as np
from siren_web.models import Analysis, Demand, DemandMatrix, facilities, FacilityStorage, Generatorattributes, \
    Scenarios, ScenariosTechnologies, ScenariosSettings, Settings, Storageattributes, \
    SupplyFactorMatrix, Technologies, TechnologyYears, variations
from siren_web.services.supply_matrix import facility_row_index, load_year_matrix
from siren_web.services import demand_matrix
from powermatchui.views.balance_grid_load import Technology

def delete_analysis_scenario(idscenario):
    Analysis.objects.filter(
        idscenarios=idscenario
    ).delete()
    variations.objects.filter(
        idscenarios=idscenario
    ).delete()
    return None

def fetch_analysis_scenario(scenario):
    scenario_obj = get_scenario_by_title(scenario)
    analysis_list = Analysis.objects.filter(
        idscenarios=scenario_obj
    ).all()[:20]
    return analysis_list

def check_analysis_baseline(scenario):
    scenario_obj = get_scenario_by_title(scenario)
    baseline = Analysis.objects.filter(
        idscenarios=scenario_obj,
        variation='Baseline'
    )[:1]
    return baseline

def fetch_facilities_scenario(scenario):
    scenario_obj = get_scenario_by_title(scenario)
    facilities_list = facilities.objects.filter(
        scenarios=scenario_obj
    ).all()
    return facilities_list
 
def fetch_facilities_generator_storage_data(demand_year):
    facilities_query = \
    f"""
    WITH fte AS (
        SELECT 
            f.*,  -- Select all fields from facilities
            t.technology_name,  -- Select all fields from Technologies
            ga.fuel, sa.discharge_loss,
            COALESCE(sa.year, ga.year) AS year,
            t.area,
            ROW_NUMBER() OVER (PARTITION BY f.facility_name ORDER BY year DESC) AS row_num
        FROM 
            facilities f
        INNER JOIN 
            Technologies t ON f.idTechnologies = t.idTechnologies
        LEFT JOIN 
            StorageAttributes sa ON t.idTechnologies = sa.idTechnologies 
            AND t.year = sa.year
            AND t.category = 'Storage'
        LEFT JOIN 
            GeneratorAttributes ga ON t.idTechnologies = ga.idTechnologies
            AND t.year = ga.year
            AND t.category = 'Generator'
        WHERE 
            t.year = %s
        )
    SELECT *
    FROM fte
    WHERE row_num = 1;
    """
    try:
        with connection.cursor() as cursor:  
            cursor.execute(facilities_query, (demand_year,) )
            # Fetch the results
            facilities_result = cursor.fetchall()
            if facilities_result is None:
                # Handle the case where fetchall() returns None
                logger = logging.getLogger(__name__)
                logger.debug('No results found.')
                return None  # or handle this case appropriately
            column_names = [desc[0] for desc in cursor.description]
        return [dict(zip(column_names, row)) for row in facilities_result]
                    
    except Exception as e:
        print("Error executing query:", e)
        
def fetch_full_facilities_data(demand_year, scenario):
    idscenarios = Scenarios.objects.get(title=scenario).idscenarios
    facilities_query = \
    f"""
    SELECT 
        f.*,  -- Select all fields from facilities
        t.technology_name,  -- Select all fields from Technologies
        ty.fuel, sa.discharge_loss,
        ty.year,
        t.area
    FROM 
        facilities f
    INNER JOIN 
        ScenariosFacilities sf ON f.idfacilities = sf.idfacilities
    INNER JOIN 
        Technologies t ON f.idTechnologies = t.idTechnologies
    INNER JOIN 
        TechnologyYears ty ON t.idTechnologies = ty.idtechnologies_id
    LEFT JOIN 
        StorageAttributes sa ON t.idTechnologies = sa.idTechnologies 
        AND t.category = 'Storage'
    LEFT JOIN 
        GeneratorAttributes ga ON t.idTechnologies = ga.idTechnologies
        AND t.category = 'Generator'
    WHERE 
        sf.idscenarios = %s
        AND ty.year = %s;
    """
    try:
        with connection.cursor() as cursor:  
            cursor.execute(facilities_query, (idscenarios, demand_year) )
            # Fetch the results
            facilities_result = cursor.fetchall()
            if facilities_result is None:
                # Handle the case where fetchall() returns None
                logger = logging.getLogger(__name__)
                logger.debug('No results found.')
                return None  # or handle this case appropriately
            column_names = [desc[0] for desc in cursor.description]
        return [dict(zip(column_names, row)) for row in facilities_result]
                    
    except Exception as e:
        print("Error executing query:", e)

def get_scenario_by_title(scenario):
    try:
        return Scenarios.objects.get(title=scenario)
    except Exception as e:
        print(f"Error fetching title for scenario '{scenario}': {e}")
 
def _expected_intervals_per_year(interval_minutes):
    """Number of dispatch intervals in a (365-day) year at the given
    scenario resolution, e.g. 8760 for hourly, 17520 for half-hourly."""
    return 8760 * 60 // interval_minutes


def _upsample_column_if_needed(values, interval_minutes):
    """
    FR-G1 resolution shim: a scenario's Load facility may be stored at
    interval_minutes resolution (e.g. 30 for an ESOO-derived demand trace)
    while other facilities already in the same scenario (wind/solar/
    storage) are still stored at the legacy hourly resolution (8760
    supplyfactors rows/year), since they were generated before this
    scenario existed and don't need regenerating.

    When that mismatch is detected (interval_minutes != 60 but this
    column's row count still matches an hourly year), each hourly value is
    repeated across its sub-hourly slots so every column in load_and_supply
    ends up the same length. This is a stated simplification, not a real
    resample: it assumes the supply-side shape is constant within the hour
    it was stored for, so sub-hourly demand/supply shape correlation
    (e.g. a solar ramp partway through an hour) isn't modelled. Callers
    that need genuine sub-hourly supply-side shape must regenerate that
    facility's supplyfactors at the finer resolution instead of relying on
    this shim.

    For interval_minutes == 60 (every scenario created before this field
    existed), this is always a no-op: the expected count already equals
    the stored count, so the branch below never triggers.
    """
    if interval_minutes == 60:
        return values

    expected = _expected_intervals_per_year(interval_minutes)
    n = len(values)
    if n == expected or n == 0:
        return values

    # Hourly-stored column (8760, or 8784 in a leap year) being consumed by
    # a finer-resolution scenario: repeat each value across its sub-hourly
    # slots. Only handles a clean integer up-sampling factor; anything else
    # is left untouched rather than guessed at.
    if expected % n == 0:
        factor = expected // n
        return [v for v in values for _ in range(factor)]

    # Row count doesn't match either the native hourly count or the
    # target resolution and isn't a clean multiple — leave as-is rather
    # than silently misalign the trace; the dispatch loop will simply see
    # a shorter column than expected for this technology.
    return values


def _resample_column(values, source_interval_minutes, target_interval_minutes):
    """
    Resample an explicit demand-override column (see resolve_demand_override)
    from its own known native resolution to the base scenario's
    interval_minutes. Unlike _upsample_column_if_needed above, the source
    resolution here is always known up front rather than inferred from row
    count against an assumed-hourly source.

    - Equal resolutions: no-op.
    - target coarser than source (e.g. base=60min, override=30min):
      downsample by averaging each run of `factor` consecutive source
      values. ESOO/EV traces are average-MW per interval (not energy — see
      esoo_scenario_views.build_reference_shape's docstring), so an hourly
      average is exactly the mean of its two half-hourly averages.
    - target finer than source: upsample by repeating each value, mirroring
      _upsample_column_if_needed's own documented simplification.
    - any other ratio, or a value count that doesn't divide evenly: left
      unresampled — the mismatch surfaces as a short/long column rather
      than being silently misaligned.
    """
    if not values or source_interval_minutes == target_interval_minutes:
        return values

    n = len(values)
    if target_interval_minutes > source_interval_minutes:
        factor = target_interval_minutes // source_interval_minutes
        if target_interval_minutes % source_interval_minutes or n % factor:
            return values
        arr = np.asarray(values, dtype=float).reshape(-1, factor)
        return np.nanmean(arr, axis=1).tolist()
    else:
        factor = source_interval_minutes // target_interval_minutes
        if source_interval_minutes % target_interval_minutes:
            return values
        return [v for v in values for _ in range(factor)]


@dataclass
class DemandOverride:
    """The Demand selected to dispatch a run against, resolved by
    resolve_demand_override. A Demand has no schema-level link to any
    Scenarios row -- this is always a per-run choice, and this dataclass
    only affects the load_and_supply[0] column fetch_supplyfactors_data
    builds for one dispatch run."""
    demand_id: int
    year: int                 # the DemandMatrix year that actually holds this Demand's trace
    interval_minutes: int     # the Demand's own native resolution
    demand_name: str
    reference_year: int = None  # ESOO-built Demands only -- see Demand.reference_year


def resolve_demand_override(demand_id):
    """
    Resolve a Demand PK (typically session['demand_scenario_demand_id'])
    into a DemandOverride, or None if demand_id is falsy/stale/traceless.
    Callers must treat None as "no demand selected -- this run cannot
    proceed" (see fetch_supplyfactors_data) — this never raises.

    The override's year is discovered by probing every DemandMatrix year
    for this Demand's presence, NOT taken from the caller's demand_year:
    AEMO ESOO/EV demand traces are written keyed by their own
    forecast_year (see esoo_scenario_views.build_scenario_from_esoo /
    ev_scenario_views.build_scenario_from_ev), which is independent of
    whatever year is currently driving the base supply scenario's matrix
    load.
    """
    if not demand_id:
        return None
    try:
        demand_obj = Demand.objects.get(pk=demand_id)
    except Demand.DoesNotExist:
        logging.warning(f"Demand override id {demand_id} no longer exists; ignoring.")
        return None

    for year in DemandMatrix.objects.order_by('-year').values_list('year', flat=True):
        if demand_matrix.demand_has_trace(year, demand_obj.iddemand):
            return DemandOverride(
                demand_id=demand_obj.iddemand,
                year=year,
                interval_minutes=demand_obj.interval_minutes or 30,
                demand_name=demand_obj.name,
                reference_year=demand_obj.reference_year,
            )

    logging.warning(
        f"Demand '{demand_obj.name}' has no trace in any DemandMatrix year; ignoring."
    )
    return None


def resolve_baseline_year(scenario, weather_year=None):
    """
    The year that drives technology-cost lookups (fetch_technology_attributes)
    and the base scenario's OWN supply-side SupplyFactorMatrix retrieval
    (fetch_supplyfactors_data's initial load_year_matrix(demand_year) call,
    which finds this scenario's own wind/solar/storage facility rows).

    Takes the session-selected weather_year (request.session['weather_year'],
    set via DemandScenarioSettings/WeatherScenarioSettings) as an explicit
    argument, rather than reading Scenarios.weather_year as before:
    Scenarios.forecast_year now means the scenario's build-out/target year
    (e.g. 2035 for an auto-generated Facilities Take-up scenario, which has
    no SupplyFactorMatrix data for 2035), not a real weather-trace year, so
    it can no longer supply this value. Callers pass
    request.session.get('weather_year').

    Deliberately unrelated to any active demand_override: a demand override
    gets its own independent load_year_matrix(demand_override.year) lookup
    inside fetch_supplyfactors_data, scoped to just the Load column. Using
    the override's year here instead of the session weather_year would make
    fetch_supplyfactors_data load the WRONG year's matrix for every other
    technology.

    Returns None if it can't be determined (scenario not found, or
    weather_year not set) — callers must treat that as "can't run", not
    silently pick a default.
    """
    scenario_obj = Scenarios.objects.filter(title=scenario).first()
    if scenario_obj is None:
        return None
    return int(weather_year) if weather_year else None


def get_demand_scenario_context(request):
    """
    Demand-selection context (a DemandScenarioOverrideForm plus the
    currently-selected Demand's display name) shared by every page that
    lets the user set/see session['demand_scenario_demand_id'] -- currently
    powermatchui's Baseline Scenario page and powermapui's Run Power page.
    See resolve_demand_override / resolve_baseline_year for how the
    selection is actually applied.
    """
    from siren_web.forms import DemandScenarioOverrideForm

    demand_id = request.session.get('demand_scenario_demand_id')
    selected_demand = (
        Demand.objects.filter(pk=demand_id).first() if demand_id else None
    )
    return {
        'demand_scenario_form': DemandScenarioOverrideForm(initial={
            'demand_scenario_demand': demand_id
        }),
        'selected_demand_scenario_title': (
            selected_demand.name if selected_demand else None
        ),
    }


def fetch_supplyfactors_data(demand_year, scenario, demand_override=None):
    """
    Build load_and_supply: {merit_order: [value per hour/interval, ...]}
    for every technology in this scenario's merit order, read from the
    packed per-year SupplyFactorMatrix instead of the row-per-hour
    supplyfactors table.

    A merit-order slot can span more than one facility of the same
    technology (e.g. several Gas OCGT plants) — those are summed per hour
    via the matrix, which is what balance_grid_load.py's positional
    load_and_supply[merit_order][h] indexing has always assumed. The
    previous supplyfactors-based implementation instead appended every
    facility's rows into one list ordered only by hour, so a multi-facility
    merit-order group produced an oversized, misaligned column; this fixes
    that as part of the cutover rather than reproducing it.
    """
    try:
        # This table is small (~6 rows) so we can afford to load it all
        scenarios_tech_query, scenario_obj = fetch_scenario_technologies(scenario)

        interval_minutes = getattr(scenario_obj, 'interval_minutes', 60) or 60

        try:
            matrix_facility_ids, matrix = load_year_matrix(demand_year)
        except SupplyFactorMatrix.DoesNotExist:
            return {}

        idx = facility_row_index(matrix_facility_ids)

        load_and_supply = {}

        for st_row in scenarios_tech_query:
            merit_order = st_row.merit_order
            facility_ids = facilities.objects.filter(
                idtechnologies=st_row.idtechnologies_id,
                scenarios=scenario_obj
            ).values_list('idfacilities', flat=True)

            rows = [idx[fid] for fid in facility_ids if fid in idx]
            if not rows:
                # No supplyfactors/matrix data for this technology in this
                # year — matches the original's "merit_order key never
                # created" behaviour rather than inserting an empty column.
                continue

            load_and_supply[merit_order] = np.nansum(matrix[rows, :], axis=0).tolist()

        # Demand: the selected Demand's trace becomes the load_and_supply[0]
        # column (Load's merit_order is always 0, see
        # fetch_technology_attributes). Scenarios carry no Load facility of
        # their own any more, so this is the ONLY source of a demand
        # column -- a run with no demand_override has none at all.
        if demand_override is None:
            raise ValueError(
                "A Demand must be selected to run this scenario -- Scenarios "
                "no longer carry an implicit Load."
            )
        try:
            override_ids, override_matrix = demand_matrix.load_year_matrix(demand_override.year)
            override_idx = demand_matrix.demand_row_index(override_ids)
            row_i = override_idx.get(demand_override.demand_id)
        except DemandMatrix.DoesNotExist:
            row_i = None
        if row_i is not None:
            override_values = override_matrix[row_i, :].tolist()
            load_and_supply[0] = _resample_column(
                override_values, demand_override.interval_minutes, interval_minutes
            )
        else:
            logging.warning(
                f"Demand {demand_override.demand_id} not found in "
                f"{demand_override.year} DemandMatrix; no demand column for this run."
            )

        # Resolution shim: bring any hourly-stored columns up to this
        # scenario's interval_minutes resolution so they line up with a
        # finer-resolution Load column (see _upsample_column_if_needed).
        # No-op whenever interval_minutes == 60 (every pre-existing scenario).
        if interval_minutes != 60:
            for merit_order, values in load_and_supply.items():
                load_and_supply[merit_order] = _upsample_column_if_needed(values, interval_minutes)

    except Exception as e:
        # Handle any errors that occur during the database query
        print(f"Error fetching supplyfactors data: {e}")
        return None

    return load_and_supply

def fetch_full_generator_storage_data(demand_year):
    """
    Fetch technologies with their associated year-specific data, generator attributes,
    and storage attributes.
    
    Args:
        demand_year (int): The year to filter TechnologyYears data
        
    Returns:
        QuerySet: A queryset of Technologies objects with year data applied
    """
    # Define the SQL query
    generators_query = \
    f"""
        SELECT t.*
        FROM senasnau_siren.Technologies t
        INNER JOIN 
		TechnologyYears ty ON t.idTechnologies = ty.idtechnologies_id
        LEFT JOIN senasnau_siren.StorageAttributes s ON t.idtechnologies = s.idtechnologies 
            AND t.category = 'Storage'
        LEFT JOIN senasnau_siren.GeneratorAttributes g ON t.idtechnologies = g.idtechnologies 
            AND t.category = 'Generator'
        WHERE ty.year = %s AND
        t.category != 'Load';
    """
    # Execute the SQL query
    try:
        return Technologies.objects.raw(generators_query, [demand_year])            
    except Exception as e:
        print("Error executing query:", e)

def fetch_technology_attributes(demand_year, scenario):
    """
    Get Technology rows joined with its corresponding TechnologyYears data
    for a specific year.
    
    Args:
        demand_year (int): The year to filter TechnologyYears data
        scenario (str): The scenario to filter ScenarioTechnologies data
        
    Returns:
        dict: A merged dictionary containing Technology data with year-specific data
    """
    try:
        # Get scenario object once and reuse
        scenario_obj = Scenarios.objects.get(title=scenario)
        
        # Single query to get all needed technology data
        technologies_result = ScenariosTechnologies.objects.filter(
            idscenarios=scenario_obj,
            merit_order__lt=100
        ).select_related(
            'idtechnologies'
        ).prefetch_related(
            # Get TechnologyYears data for the specific demand_year only
            Prefetch(
                'idtechnologies__technologyyears_set',
                queryset=TechnologyYears.objects.filter(year=demand_year),
                to_attr='tech_years'
            ),
            # Get generator attributes
            Prefetch(
                'idtechnologies__generatorattributes_set',
                queryset=Generatorattributes.objects.all(),
                to_attr='generator_attrs'
            ),
            # Get storage attributes
            Prefetch(
                'idtechnologies__storage_attributes',
                queryset=Storageattributes.objects.all(),
                to_attr='storage_attrs_list'
            ),
            # Get FacilityStorage installations for this scenario's facilities
            Prefetch(
                'idtechnologies__facility_installations',
                queryset=FacilityStorage.objects.filter(
                    idfacilities__scenarios=scenario_obj,
                    is_active=True
                ).select_related('idfacilities'),
                to_attr='facility_storage_list'
            )
        ).order_by('merit_order')
        
        # Initialize dictionaries to hold results
        technology_attributes = {}
        technology_attributes['Load'] = Technology(
            category='Load',
            capacity=0,
            generator_name='Load',
            tech_type='L',
            merit_order=0,
            multiplier=1,
            # Carries the scenario's dispatch resolution through to
            # balance_grid_load.PowerMatchProcessor, which has no other
            # access to the Scenarios row. Defaults to 60 (hourly) on the
            # Scenarios model, so every pre-existing scenario behaves
            # exactly as before.
            interval_minutes=getattr(scenario_obj, 'interval_minutes', 60) or 60)
        
    except Exception as e:
        print("Error executing TechnologyYears query:", e)
        return None
        
    # Process the results
    for scenario_tech in technologies_result:
        technology_row = scenario_tech.idtechnologies
        name = technology_row.technology_name
        if name == 'Load':
            continue
        if name not in technology_attributes:
            technology_attributes[name] = {}
        
        # Get year-specific data from TechnologyYears
        tech_year_data = technology_row.tech_years[0] if technology_row.tech_years else None
        fuel = tech_year_data.fuel if tech_year_data else None
        
        # Initialize attributes with defaults
        area = technology_row.area
        capacity_max = capacity_min = None
        recharge_max = recharge_loss = discharge_max = discharge_loss = parasitic_loss = None
        
        # Get category-specific attributes
        if technology_row.category == 'Generator':
            if technology_row.generator_attrs:
                generator = technology_row.generator_attrs[0]
                capacity_max = generator.capacity_max
                capacity_min = generator.capacity_min
                
        elif technology_row.category == 'Storage':
            # Get technology-level storage attributes (efficiency, losses, constraints)
            if technology_row.storage_attrs_list:
                storage = technology_row.storage_attrs_list[0]
                recharge_max = storage.recharge_max
                recharge_loss = storage.recharge_loss
                discharge_max = storage.discharge_max
                discharge_loss = storage.discharge_loss
                parasitic_loss = storage.parasitic_loss
            
            # Aggregate facility-specific storage capacities for this scenario
            # Note: The ScenariosTechnologies.capacity already contains the aggregated
            # facility capacity, but for storage we may want power_capacity and 
            # energy_capacity separately
            total_power_capacity = 0
            total_energy_capacity = 0
            
            for facility_storage in technology_row.facility_storage_list:
                if facility_storage.power_capacity:
                    total_power_capacity += facility_storage.power_capacity
                if facility_storage.energy_capacity:
                    total_energy_capacity += facility_storage.energy_capacity
            
            # For storage, you might want to use aggregated power_capacity as capacity_max
            # and the total energy capacity separately.
            if total_power_capacity > 0:
                capacity_max = total_power_capacity
                capacity_min = 0  # Storage can typically operate from 0 to max
        
        # Get merit order (already available from the query)
        merit_order = scenario_tech.merit_order
        
        # Create Technology object using TechnologyYears data for financial parameters
        technology_attributes[name] = Technology(
            tech_id=technology_row.idtechnologies,
            tech_name=name,
            tech_signature=technology_row.technology_signature,
            tech_type=technology_row.category[0],  # 'G' for Generator, 'S' for Storage
            category=technology_row.category,
            renewable=technology_row.renewable,
            dispatchable=technology_row.dispatchable,
            capacity=scenario_tech.capacity,  # Aggregated capacity from ScenariosTechnologies
            multiplier=scenario_tech.mult,
            capacity_max=capacity_max, 
            capacity_min=capacity_min,
            lcoe=0, 
            lcoe_cfs=0,
            recharge_max=recharge_max, 
            recharge_loss=recharge_loss,
            min_runtime=0, 
            warm_time=0,
            discharge_max=discharge_max,
            discharge_loss=discharge_loss, 
            parasitic_loss=parasitic_loss,
            emissions=technology_row.emissions, 
            initial=0,
            merit_order=merit_order, 
            capex=tech_year_data.capex if tech_year_data else None,
            fixed_om=tech_year_data.fom if tech_year_data else None,
            variable_om=tech_year_data.vom if tech_year_data else None,
            fuel=fuel,
            lifetime=technology_row.lifetime, 
            area=area
        )

    return technology_attributes

def get_emission_color(emissions):
    if emissions < 0.3:
        return "#c8e6da"  # Light green
    elif emissions < 0.5:
        return "#78798a"  # Light Mauve
    elif emissions < 0.7:
        return "#6a648e"  # Mauve
    elif emissions < 0.9:
        return "#52519E"  # Dark Mauve
    else:
        return "#5C5C61"  # Grey
    
def fetch_merit_order_technologies(idscenarios):
    merit_order_data = {}
    excluded_resources_data = {}

    # Get the TechnologiesScenarios objects for the given scenario
    technologies_scenarios = ScenariosTechnologies.objects.filter(
        idscenarios=idscenarios,
        ).order_by(
            'merit_order'  # Order the results by merit_order
        )

    for technology_scenario in technologies_scenarios:
        if technology_scenario:
            technology_obj = technology_scenario.idtechnologies
            tech_category = technology_obj.category
            if (tech_category in ['Generator', 'Storage']):
                tech_id = technology_obj.idtechnologies
                emissions = technology_obj.emissions
                tech_name = technology_obj.technology_name
                merit_order = technology_scenario.merit_order
                if merit_order is not None and merit_order <= 99:
                    merit_order_data[tech_id] = [tech_name, get_emission_color(emissions)]
                else:
                    excluded_resources_data[tech_id] = [tech_name, get_emission_color(emissions)]

    return merit_order_data, excluded_resources_data

def fetch_included_technologies_data(scenario):
    """
    Fetch technologies included in a scenario with their capacities from ScenariosTechnologies
    """
    from siren_web.models import Technologies, Scenarios, ScenariosTechnologies
    
    try:
        scenario_obj = get_scenario_by_title(scenario)
        
        # Get technologies with their capacities from ScenariosTechnologies
        scenario_technologies = ScenariosTechnologies.objects.filter(
            idscenarios=scenario_obj
        ).select_related('idtechnologies')
        
        # Create a list of technology objects with capacity attribute
        technologies = []
        for st in scenario_technologies:
            tech = st.idtechnologies
            tech.capacity = st.capacity  # Add capacity from ScenariosTechnologies
            tech.mult = st.mult  # Add multiplier from ScenariosTechnologies
            technologies.append(tech)
            
        return technologies
        
    except Scenarios.DoesNotExist:
        return []

def fetch_scenario_technologies(scenario):
    """
    Fetch technologies data via ScenariosTechnologies that are part of a scenario merit order.
    """
    try:
        scenario_obj = Scenarios.objects.get(title=scenario)
        technologies = ScenariosTechnologies.objects.filter(
            idscenarios=scenario_obj,
            merit_order__lt=100
        ).select_related('idtechnologies').order_by('merit_order')
        
    except Scenarios.DoesNotExist:
        return None, None
    
    return technologies, scenario_obj

def fetch_technologies_with_multipliers(scenario):
    """
    Fetch technologies data including multipliers from ScenariosTechnologies that are part of a scenario merit order.
    """
    try:
        technologies, scenario_obj= fetch_scenario_technologies(scenario)
        # Create a list of objects with the needed attributes
        tech_list = []
        for tech in technologies:
            tech_data = tech.idtechnologies
            tech_data.capacity = tech.capacity
            tech_data.mult = tech.mult
            tech_data.pk = tech.idtechnologies.idtechnologies
            tech_list.append(tech_data)
            
        return tech_list
    
    except Scenarios.DoesNotExist:
        return []
    
def fetch_technology_by_id(idtechnologies):
    technologies = Technologies.objects.filter(
        idtechnologies=idtechnologies
    )
    return technologies
    
def fetch_generation_storage_data(demand_year):
    # Filter technologies based on merit_order conditions
    candidate_technologies = Technologies.objects.filter(
        year__in=[0, demand_year],
        category__in=['Generator', 'Storage']  # Use double underscores for related field lookups
    ).order_by('-year')
    seen_technologies = set()
    technologies = {}
    for tech in candidate_technologies:
    # Filter out duplicate technology_name rows, keeping only the one with year = demand_year
        if tech.idtechnologies not in seen_technologies:
            technologies[tech.idtechnologies] = [tech.technology_name, tech.emissions]
            seen_technologies.add(tech.idtechnologies)
    return technologies

def fetch_scenarios_data():
    try:
        scenarios = {}
        scenarios_query = Scenarios.objects.all()
        for scenario in scenarios_query:
            idscenarios = scenario.idscenarios
            title = scenario.title
            dateexported = scenario.dateexported
            description = scenario.description
            # scenarios[idscenarios] = Scenarios(idscenarios, title, dateexported, year, description)
            scenarios[idscenarios] = {
                'idscenarios': idscenarios,
                'title': title,
                'dateexported': dateexported,
                'description': description
            }
        return scenarios
    except Exception as e:
        # Handle any errors that occur during the database query
        return None

def fetch_all_settings_data():
    try:
        settings = {}
        settings_query = Settings.objects.all()
        for setting in settings_query:
            sw_context = setting.sw_context
            parameter = setting.parameter
            value = setting.value
            if sw_context not in settings:
                settings[sw_context] = {}
            settings[sw_context][parameter] = value
    except Exception as e:
        # Handle any errors that occur during the database query
        return None
    return settings

def fetch_module_settings_data(sw_context):
    try:
        settings = {}
        settings_query = Settings.objects.filter(sw_context=sw_context)
        for setting in settings_query:
            sw_context = setting.sw_context
            parameter = setting.parameter
            value = setting.value
            settings[parameter] = value
    except Exception as e:
        # Handle any errors that occur during the database query
        return None
    return settings

def fetch_scenario_settings_data(scenario):
    try:
        scenario_obj = get_scenario_by_title(scenario)
        settings = {}
        settings_query = ScenariosSettings.objects.filter(
            sw_context='Powermatch',
            scenarios=scenario_obj,
        )
        for setting in settings_query:
            sw_context = setting.sw_context
            parameter = setting.parameter
            value = setting.value
            settings[parameter] = value
    except Exception as e:
        # Handle any errors that occur during the database query
        return None
    return settings

def update_scenario_settings_data(scenario, sw_context, parameter, value):
    try:
        scenario_obj = get_scenario_by_title(scenario)
        scenario_setting_new, created = ScenariosSettings.objects.update_or_create(
                sw_context=sw_context,
                idscenarios=scenario_obj,
                parameter=parameter,
                defaults={'value': value}
            )
    except Exception as e:
        # Handle any errors that occur during the database query
        return None
    return scenario_setting_new

def fetch_variations_list(scenario):
    try:
        variations_list = variations.objects.all()
    except Exception as e:
        # Handle any errors that occur during the database query
        return None
    return variations_list

def fetch_variation(variation):
    try:
        variation = variations.objects.filter(
            variation_name=variation
        )
    except Exception as e:
        # Handle any errors that occur during the database query
        return None
    return variation