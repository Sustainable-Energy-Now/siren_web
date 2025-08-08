# database operations
from configparser import ConfigParser
from django.db import connection
from django.db.models import Prefetch
import logging
from django.db.models import Avg, Q, F, Sum, Count, When, OuterRef, Subquery
from django.db.models.functions import TruncDay
import os
from siren_web.models import Analysis, facilities, Generatorattributes, Optimisations, \
    Scenarios, ScenariosTechnologies, ScenariosSettings, Settings, Storageattributes, supplyfactors, \
    Technologies, TechnologyYears, TradingPrice, variations, Zones
from siren_web.siren.powermatch.logic.logic import Constraint, Optimisation
from powermatchui.views.balance_grid_load import Technology

def delete_analysis_scenario(idscenario):
    Analysis.objects.filter(
        idscenarios=idscenario
    ).delete()
    variations.objects.filter(
        idscenarios=idscenario
    ).delete()
    return None

def fetch_analysis_scenario(idscenario):
    analysis_list = Analysis.objects.filter(
        idscenarios=idscenario
    ).all()
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
 
def get_supply_unique_technology(demand_year, scenario):
    # Get the scenario object
    scenario_obj = get_scenario_by_title(scenario)

    # Filter the SupplyFactors objects for the given demand_year and scenario
    unique_technologies = Technologies.objects.filter(
        id__in=supplyfactors.objects.values('idtechnologies')
                                    .annotate(count=Count('idtechnologies'))
                                    .filter(count__gt=0, year=demand_year, idscenarios=scenario_obj)
                                    .distinct()
    )
    return unique_technologies

def get_supply_by_technology(demand_year, scenario):
    # Get the scenario object
    scenario_obj = get_scenario_by_title(scenario)

    # Filter the SupplyFactors objects for the given demand_year and scenario
    supplyfactors_queryset = supplyfactors.objects.filter(year=demand_year, idscenarios=scenario_obj)

    # Calculate the total load by technology
    total_supply_by_technology = \
        supplyfactors_queryset.values('idtechnologies').annotate(total_supply=Sum('quantum'))

    return total_supply_by_technology

def fetch_supplyfactors_data(demand_year, scenario):
    try:
        # Cache ScenariosTechnologies data for efficient lookup
        # This table is small (~6 rows) so we can afford to load it all

        scenarios_tech_query, scenario_obj = fetch_scenario_technologies(scenario)
        
        # Create lookup dictionaries for merit order by technology ID
        tech_merit_order_lookup = {}
        tech_capacity_lookup = {}
        
        for st_row in scenarios_tech_query:
            tech_id = st_row.idtechnologies.idtechnologies
            tech_merit_order_lookup[tech_id] = st_row.merit_order
            tech_capacity_lookup[tech_id] = st_row.capacity
        
        # Read supplyfactors table using Django ORM
        # Filter by facilities that are associated with the scenario
        supplyfactors_query = supplyfactors.objects.filter(
            year=demand_year,
            idfacilities__scenarios=scenario_obj  # Only facilities in this scenario
        ).select_related(
            'idfacilities__idtechnologies'  # Join with Technologies through facilities
        ).order_by(
            'hour'  # Order by hour
        )
        
        # Create a dictionary of supplyfactors from the model 
        load_and_supply = {}
        
        for supplyfactors_row in supplyfactors_query:
            technology = supplyfactors_row.idfacilities.idtechnologies
            name = technology.technology_name
            tech_id = technology.idtechnologies
            
            # Look up mult and merit order from our cached ScenariosTechnologies data
            merit_order = tech_merit_order_lookup.get(tech_id)
            
            # Skip if this technology doesn't have merit_order data in ScenariosTechnologies
            if merit_order is None:
                continue
                
            load = supplyfactors_row.quantum
            
            if merit_order not in load_and_supply:
                load_and_supply[merit_order] = []
            load_and_supply[merit_order].append(load)
            
    except Exception as e:
        # Handle any errors that occur during the database query
        print(f"Error fetching supplyfactors data: {e}")
        return None

    return load_and_supply

def get_all_technologies_for_year(demand_year):
    """
    Get all Technology rows joined with their corresponding TechnologyYears data
    for a specific year.
    
    Args:
        demand_year (int): The year to filter TechnologyYears data
        
    Returns:
        list: A list of merged dictionaries containing Technology data with year-specific data
    """
    # Use a more efficient approach with select_related to minimize database hits
    tech_years = TechnologyYears.objects.filter(
        year=demand_year
    ).select_related('idtechnologies')
    
    result = []
    for tech_year in tech_years:
        technology = tech_year.idtechnologies
        
        # Create a merged dictionary with data from both tables
        tech_data = {
            'idtechnologies': technology.idtechnologies,
            'technology_name': technology.technology_name,
            'technology_signature': technology.technology_signature,
            'image': technology.image,
            'caption': technology.caption,
            'category': technology.category,
            'renewable': technology.renewable,
            'dispatchable': technology.dispatchable,
            'description': technology.description,
            'area': technology.area,
            # Include year-specific data
            'year': tech_year.year,
            'capex': tech_year.capex,
            'fom': tech_year.fom,
            'vom': tech_year.vom,
            'lifetime': tech_year.lifetime,
            'discount_rate': tech_year.discount_rate,
            'capacity': tech_year.capacity,
            'capacity_factor': tech_year.capacity_factor,
            'mult': tech_year.mult,
            'approach': tech_year.approach,
            'capacity_max': tech_year.capacity_max,
            'capacity_min': tech_year.capacity_min,
            'capacity_step': tech_year.capacity_step,
            'capacities': tech_year.capacities,
            'emissions': tech_year.emissions,
            'initial': tech_year.initial,
            'lcoe': tech_year.lcoe,
            'lcoe_cf': tech_year.lcoe_cf,
        }
        
        result.append(tech_data)
        
    return result

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
                'idtechnologies__storageattributes_set',
                queryset=Storageattributes.objects.all(),
                to_attr='storage_attrs'
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
            multiplier=1)
        
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
        recharge_max = recharge_loss = discharge_max = discharge_loss = parasitic_loss = None
        
        # Get category-specific attributes
        if technology_row.category == 'Generator':
            if technology_row.generator_attrs:
                generator = technology_row.generator_attrs[0]
                
        elif technology_row.category == 'Storage':
            if technology_row.storage_attrs:
                storage = technology_row.storage_attrs[0]
                recharge_max = storage.recharge_max
                recharge_loss = storage.recharge_loss
                discharge_max = storage.discharge_max
                discharge_loss = storage.discharge_loss
                parasitic_loss = storage.parasitic_loss
        
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
            capacity=scenario_tech.capacity,
            multiplier=scenario_tech.mult,
            capacity_max=generator.capacity_max, 
            capacity_min=generator.capacity_min,
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
            # initial=technology_row.initial,
            initial=0,
            merit_order=merit_order, 
            capex=tech_year_data.capex,
            fixed_om=tech_year_data.fom,
            variable_om=tech_year_data.vom,
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

def fetch_config_path(request):
    try:
        config_file = request.session.get('config_file')
        if not config_file:
            config_file = 'siren.ini'
        config_dir = './siren_web/siren_files/preferences/'
        config_path = os.path.join(config_dir, config_file)
        if not os.path.exists(config_path):
            return None
    except Exception as e:
        # Handle any errors that occur during the database query
        return None
    return config_path

def fetch_all_config_data(request):
    try:
        config_path = fetch_config_path (request)
        config = ConfigParser()
        config.read(config_path)
    except Exception as e:
        # Handle any errors that occur during the database query
        return None
    return config

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

def fetch_optimisation_data(scenario):
    try:
        scenario_obj = get_scenario_by_title(scenario)
        # Get the list of included technologies
        optimisation_data = Technologies.objects \
            .values(
                'idtechnologies', 'technology_name', 'approach', 'capacity', 'capacity_max','capacity_min', 
                'capacity_step', 'capacities').filter(
            scenarios=scenario_obj,
            # category__in=['Generator', 'Storage'],  # Use double underscores for related field lookups
            scenariostechnologies__merit_order__lt=100
        ).order_by('scenariostechnologies__merit_order')
    except Exception as e:
        # Handle any errors that occur during the database query
        return None
    return optimisation_data

def update_optimisation_data(scenario, idtechnologies, approach, capacity, capacity_max, capacity_min, capacity_step,
    capacities):
    Technology = Technologies.objects.get(idtechnologies=idtechnologies)
    Technology.approach = approach
    Technology.capacity = capacity
    Technology.capacity_max = capacity_max
    Technology.capacity_min = capacity_min
    Technology.capacity_step = capacity_step
    Technology.capacities = capacities
    Technology.save
    return Technology

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

def get_monthly_average_reference_price():  
    # Query to calculate daily average reference_price for each day within the specified month
    average_prices = (
        TradingPrice.objects
        .all()
        .annotate(day=TruncDay('trading_interval'))
        .values('day')
        .annotate(avg_price=Avg('reference_price'))
        .order_by('day')
    )
    return average_prices