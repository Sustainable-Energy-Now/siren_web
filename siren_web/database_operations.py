# In powermatchui database operations
from django.db import connection
from django.http import HttpResponse
import logging
from django.db.models import Q, F
from siren_web.models import Analysis, Demand, facilities, Scenarios, ScenariosTechnologies, ScenariosSettings, Settings, Technologies, Zones
from powermatchui.powermatch.pmcore import Facility, PM_Facility, Optimisation

def delete_analysis_scenario(idscenario):
    Analysis.objects.filter(
        idscenarios=idscenario
    ).delete()
    return None

def fetch_analysis_scenario(idscenario):
    analysis_list = Analysis.objects.filter(
        idscenarios=idscenario
    ).all()
    return analysis_list

def fetch_demand_data(demand_year):
    # Check if demand is already stored in session
    try:
        # Read demand table using Django ORM
        demand_query = Demand.objects.filter(
        ).select_related(
            'idtechnologies'  # Perform join with Technologies
        ).order_by(
            'col', 'hour'  # Order the results by col and hour
        )
        # Create a dictionary of Demand from the model 
        pmss_data = {}
        pmss_details = {} # contains name, generator, capacity, fac_type, col, multiplier
        pmss_details['Load'] = PM_Facility('Load', 'Load', 1, 'L', 0, 1)
        for demand_row in demand_query:
            name = demand_row.idtechnologies.technology_name
            idtechnologies = demand_row.idtechnologies.idtechnologies
            col = demand_row.col
            load = demand_row.load
            if col not in pmss_data:
                pmss_data[col] = []
            pmss_data[col].append(load)
            if (name != 'SWIS'):
                if name not in pmss_details: # type: ignore
                    capacity = demand_row.idtechnologies.capacity
                    pmss_details[name] = PM_Facility(name, name, capacity, 'R', col, 1)
    except Exception as e:
        # Handle any errors that occur during the database query
        return HttpResponse(f"Error fetching demand data: {e}", status=500), None
    
    return pmss_data, pmss_details
        
def relate_technologies_to_scenario(idscenarios):
    # Query to fetch distinct idTechnologies from facilities for a given scenario
    try:
        scenario = Scenarios.objects.get(idscenarios=idscenarios)
        # Get the distinct technologies for facilities that have the given scenario
        distinct_tech_ids = facilities.objects.filter(
             scenarios=idscenarios
         ).values_list(
             'idtechnologies', flat=True).distinct()
        # distinct_tech_ids = facilities.objects.filter(
        #     scenarios=idscenarios
        # ).filter(Q(technologies__category='Generator') | Q(technologies__category='Storage')).values_list(
        #     'idtechnologies', flat=True).distinct()
        # Get the Technology instances for the distinct ids
        technologies = Technologies.objects.filter(idtechnologies__in=distinct_tech_ids)
        # Remove existing relationships for technologies not in the list
        ScenariosTechnologies.objects.filter(
            idscenarios=scenario
        ).exclude(
            idtechnologies__in=technologies
        ).delete()
            # Create relationships for technologies not already associated
        existing_relationships = ScenariosTechnologies.objects.filter(
            idscenarios=scenario
        ).values_list('idtechnologies', flat=True)

        for tech in technologies:
            if tech.idtechnologies not in existing_relationships:
                ScenariosTechnologies.objects.create(
                    idscenarios=scenario,
                    idtechnologies=tech
                )

        return technologies
    except Exception as e:
        return None
    
def fetch_full_generator_storage_data(demand_year):
    # Define the SQL query
    generators_query = \
    f"""
        WITH cte AS (
        SELECT t.*,
        s.discharge_loss,
        s.discharge_max, s.parasitic_loss, s.rampdown_max,
        s.rampup_max, s.recharge_loss, s.recharge_max,
        s.min_runtime, s.warm_time,
        g.fuel,
        ROW_NUMBER() OVER (PARTITION BY t.technology_name ORDER BY t.merit_order, t.year DESC) AS row_num
        FROM senasnau_siren.Technologies t
        LEFT JOIN senasnau_siren.StorageAttributes s ON t.idtechnologies = s.idtechnologies 
            AND t.category = 'Storage' AND t.year = s.year
        LEFT JOIN senasnau_siren.GeneratorAttributes g ON t.idtechnologies = g.idtechnologies 
            AND t.category = 'Generator' AND t.year = g.year
        WHERE t.year IN (0, {demand_year}) AND
        t.category != 'Load'
        )
        SELECT *
        FROM cte
        WHERE row_num = 1;
    """
    # Execute the SQL query
    try:
        with connection.cursor() as cursor:
            cursor.execute(generators_query)
            # Fetch the results
            generators_result = cursor.fetchall()
            if generators_result is None:
                # Handle the case where fetchall() returns None
                logger = logging.getLogger(__name__)
                logger.debug('No results found.')
                return None, None  # or handle this case appropriately
            column_names = [desc[0] for desc in cursor.description]
        return generators_result, column_names
                    
    except Exception as e:
        print("Error executing query:", e)
        # Get the column names

def get_emission_color(emissions):
    if emissions < 0.3:
        return '#c8e6c9'  # Light green
    elif emissions < 0.5:
        return '#81c784'  # Green
    elif emissions < 0.7:
        return '#4caf50'  # Dark green
    elif emissions < 0.9:
        return '#388e3c'  # Greenish black
    else:
        return '#1b5e20'  # Black
    
def fetch_merit_order_technologies(demand_year, idscenarios):
    merit_order_data = {}
    excluded_resources_data = {}

    # Get the TechnologiesScenarios objects for the given scenario
    technologies_scenarios = ScenariosTechnologies.objects.filter(idscenarios=idscenarios).order_by(
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
    # Get the list of included technologies
    scenario_obj = Scenarios.objects.get(title=scenario)
    technologies_list = Technologies.objects.filter(
        scenarios=scenario_obj,
        category__in=['Generator', 'Storage'],  # Use double underscores for related field lookups
        scenariostechnologies__merit_order__lt=100
    ).order_by('scenariostechnologies__merit_order')
    return technologies_list

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

def fetch_Storage_IDs_list(demand_year):
    storage_technologies = Technologies.objects.filter(
        category='Storage',
        year__in=[0, demand_year]
    ).values_list(
             'idtechnologies', flat=True).distinct()
    return storage_technologies

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
        scenario_obj = Scenarios.objects.get(title=scenario)
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