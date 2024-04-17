# In powermatchui database operations
from django.db import connection
from django.http import HttpResponse
import logging
from django.db.models import Q, F, Sum, Count
from siren_web.models import Analysis, Demand, facilities, Generatorattributes, Scenarios, \
    ScenariosTechnologies, ScenariosSettings, Settings, Storageattributes, supplyfactors, \
    Technologies, variations, Zones
from powermatchui.powermatch.pmcore import PM_Facility, Optimisation

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
    scenario_obj = Scenarios.objects.get(title=scenario)
    baseline = Analysis.objects.filter(
        idscenarios=scenario_obj,
        variation='Baseline'
    )[:1]
    return baseline

def get_supply_unique_technology(demand_year, scenario):
    # Get the scenario object
    scenario_obj = Scenarios.objects.get(title=scenario)

    # Filter the Demand objects for the given demand_year and scenario
    unique_technologies = Technologies.objects.filter(
        id__in=supplyfactors.objects.values('idtechnologies')
                                    .annotate(count=Count('idtechnologies'))
                                    .filter(count__gt=0, year=demand_year, idscenarios=scenario_obj)
                                    .distinct()
    )
    return unique_technologies

def get_supply_by_technology(demand_year, scenario):
    # Get the scenario object
    scenario_obj = Scenarios.objects.get(title=scenario)

    # Filter the Demand objects for the given demand_year and scenario
    supplyfactors_queryset = supplyfactors.objects.filter(year=demand_year, idscenarios=scenario_obj)

    # Calculate the total load by technology
    total_supply_by_technology = \
        supplyfactors_queryset.values('idtechnologies').annotate(total_supply=Sum('quantum'))

    return total_supply_by_technology

def fetch_supplyfactors_data(demand_year):
    try:
        # Read supplyfactors table using Django ORM
        supplyfactors_query = supplyfactors.objects.filter(
        ).select_related(
            'idtechnologies'  # Perform join with Technologies
        ).order_by(
            'col', 'hour'  # Order the results by col and hour
        )
        # Create a dictionary of supplyfactors from the model 
        pmss_data = {}
        pmss_details = {} # contains name, generator, capacity, fac_type, col, multiplier
        pmss_details['Load'] = PM_Facility('Load', 'Load', 1, 'L', 0, 1)
        for supplyfactors_row in supplyfactors_query:
            name = supplyfactors_row.idtechnologies.technology_name # type: ignore
            idtechnologies = supplyfactors_row.idtechnologies.idtechnologies
            col = supplyfactors_row.col
            load = supplyfactors_row.quantum
            if col not in pmss_data:
                pmss_data[col] = []
                max_col = col
            pmss_data[col].append(load)
            if (name != 'Load'):
                if name not in pmss_details: # type: ignore
                    capacity = supplyfactors_row.idtechnologies.capacity
                    pmss_details[name] = PM_Facility(name, name, capacity, 'R', col, 1)
    except Exception as e:
        # Handle any errors that occur during the database query
        return HttpResponse(f"Error fetching supplyfactors data: {e}", status=500), None
    
    return pmss_data, pmss_details, max_col

def copy_technologies_from_year0(idtechnologies, demand_year, scenario):
    scenario_obj = Scenarios.objects.get(title=scenario)
    try:
        technology_year0 = Technologies.objects.get(
            idtechnologies=idtechnologies,
            year=0
            )
    except Exception as e:
        # Assume it is the demand_year
        return idtechnologies
    technology_new, created = Technologies.objects.get_or_create(
        technology_name=technology_year0.technology_name,
        year=demand_year,
        defaults={
            'idtechnologies': None,
            'technology_name': technology_year0.technology_name,
            'technology_signature': technology_year0.technology_signature,
            # 'scenarios': technology_year0.scenarios,
            'image': technology_year0.image,
            'caption': technology_year0.caption,
            'category': technology_year0.category,
            'renewable': technology_year0.renewable,
            'dispatchable': technology_year0.dispatchable,
            'capex': technology_year0.capex,
            'fom': technology_year0.fom,
            'vom': technology_year0.vom,
            'lifetime': technology_year0.lifetime,
            'discount_rate': technology_year0.discount_rate,
            'description': technology_year0.description,
            'mult': technology_year0.mult,
            'capacity': technology_year0.capacity,
            'capacity_max': technology_year0.capacity_max,
            'capacity_min': technology_year0.capacity_min,
            'emissions': technology_year0.emissions,
            'initial': technology_year0.initial,
            'lcoe': technology_year0.lcoe,
            'lcoe_cf': technology_year0.lcoe_cf,
        }
    )
    if created:
    # Add the scenario
        technology_new.scenarios.add(scenario_obj)
        # if the created technology is a Generator also create the GeneratorAttributes
        if technology_new.category == 'Generator':
            old_genattr = Generatorattributes(
                idtechnologies=technology_year0
            )
            new_genattr = Generatorattributes.objects.create(
                idtechnologies=technology_new,
                year=demand_year,
                fuel=old_genattr.fuel
            )
        if technology_new.category == 'Storage':
            old_storattr = Storageattributes(
                idtechnologies=technology_year0
            )
            new_storattr = Storageattributes.objects.create(
                idtechnologies=technology_new,
                year=demand_year,
                discharge_loss=old_storattr.discharge_loss,
                discharge_max=old_storattr.discharge_max,
                parasitic_loss=old_storattr.parasitic_loss,
                rampdown_max=old_storattr.rampdown_max,
                rampup_max=old_storattr.rampup_max,
                recharge_loss=old_storattr.recharge_loss,
                recharge_max=old_storattr.recharge_max,
                min_runtime=old_storattr.min_runtime,
                warm_time=old_storattr.warm_time,
            )
            # Update/create the technology foreign keys in ScenariosTechnologies
            ScenariosTechnologies.objects.filter(
                idscenarios=scenario_obj,
                idtechnologies=technology_year0
                ).update(
                    idtechnologies=technology_new
                )
    return technology_new

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
    # Get the list of included technologies
    scenario_obj = Scenarios.objects.get(title=scenario)
    technologies_list = Technologies.objects.filter(
        scenarios=scenario_obj,
        # category__in=['Generator', 'Storage'],  # Use double underscores for related field lookups
        scenariostechnologies__merit_order__lt=100
    ).order_by('scenariostechnologies__merit_order')
    return technologies_list

def fetch_technology_by_id(idtechnologies):
    technologies = Technologies.objects.filter(
        idtechnologies=idtechnologies
    ).order_by('-year')
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

def update_scenario_settings_data(scenario, sw_context, parameter, value):
    try:
        scenario_obj = Scenarios.objects.get(title=scenario)
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