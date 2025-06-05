# database operations
from configparser import ConfigParser
from datetime import datetime, timedelta
from decimal import Decimal
from django.db import connection, models
from django.db.models import Prefetch
from django.http import HttpResponse
import logging
from django.db.models import Avg, Q, F, Sum, Count, When, OuterRef, Subquery
from django.db.models.query import RawQuerySet
from django.db.models.functions import TruncDay
import os
from siren_web.models import Analysis, Demand, facilities, Generatorattributes, Optimisations, \
    Scenarios, ScenariosTechnologies, ScenariosSettings, Settings, Storageattributes, supplyfactors, \
    Technologies, TechnologyYears, TradingPrice, variations, Zones
from siren_web.siren.powermatch.logic.logic import Constraint, Facility, PM_Facility, Optimisation
from typing import Dict

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

def fetch_facilities_scenario(scenario):
    scenario_obj = Scenarios.objects.get(title=scenario)
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
        supplyfactors_query = supplyfactors.objects.filter(year=demand_year
        ).select_related(
            'idtechnologies'  # Perform join with Technologies
        ).order_by(
            'col', 'hour'  # Order the results by col and hour
        )
        # Create a dictionary of supplyfactors from the model 
        pmss_data = {}
        pmss_details = {} # contains name, generator, capacity, fac_type, col, multiplier
        pmss_details['Load'] = PM_Facility('Load', 'Load', 1, 'L', 0, float(1.0))
        for supplyfactors_row in supplyfactors_query:
            name = supplyfactors_row.idtechnologies.technology_name # type: ignore
            idtechnologies = supplyfactors_row.idtechnologies.idtechnologies
            multiplier = float(supplyfactors_row.idtechnologies.mult)
            col = supplyfactors_row.col
            load = supplyfactors_row.quantum
            if col not in pmss_data:
                pmss_data[col] = []
                max_col = col
            pmss_data[col].append(load)
            if (name != 'Load'):
                if name not in pmss_details: # type: ignore
                    capacity = supplyfactors_row.idtechnologies.capacity
                    pmss_details[name] = PM_Facility(name, name, capacity, 'R', col, multiplier)
    except Exception as e:
        # Handle any errors that occur during the database query
        return HttpResponse(f"Error fetching supplyfactors data: {e}", status=500), None
    
    return pmss_data, pmss_details, max_col

def get_technology_with_year_data(idtechnologies, demand_year):
    """
    Get a specific Technology row joined with its corresponding TechnologyYears data
    for a specific year using Django ORM.
    
    Args:
        idtechnologies (int): The primary key of the Technology
        demand_year (int): The year to filter TechnologyYears data
        
    Returns:
        dict: A merged dictionary containing Technology data with year-specific data
    """
    try:
        # Get the base technology
        technology = Technologies.objects.get(idtechnologies=idtechnologies)
        
        # Get the year-specific data
        try:
            tech_year = TechnologyYears.objects.get(
                idtechnologies=technology,
                year=demand_year
            )
        except TechnologyYears.DoesNotExist:
            # Try to get data for year 0 as fallback
            tech_year = TechnologyYears.objects.get(
                idtechnologies=technology,
                year=0
            )
        
        # Check for storage attributes if applicable
        storage_attrs = None
        if technology.category == 'Storage':
            try:
                storage_attrs = Storageattributes.objects.get(idtechnologies=technology)
            except Storageattributes.DoesNotExist:
                pass
        
        # Check for generator attributes if applicable
        generator_attrs = None
        if technology.category == 'Generator':
            try:
                generator_attrs = Generatorattributes.objects.get(idtechnologies=technology)
            except Generatorattributes.DoesNotExist:
                pass
        
        # Get merit order from ScenariosTechnologies if available
        merit_order = None
        try:
            scenario_tech = ScenariosTechnologies.objects.filter(
                idtechnologies=technology
            ).first()
            if scenario_tech:
                merit_order = scenario_tech.merit_order
        except Exception:
            pass
        
        # Create a dictionary of the technology data
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
            'merit_order': merit_order
        }
        
        # Add storage attributes if available
        if storage_attrs:
            tech_data.update({
                'discharge_loss': storage_attrs.discharge_loss,
                'discharge_max': storage_attrs.discharge_max,
                'parasitic_loss': storage_attrs.parasitic_loss,
                'rampdown_max': storage_attrs.rampdown_max,
                'rampup_max': storage_attrs.rampup_max,
                'recharge_loss': storage_attrs.recharge_loss,
                'recharge_max': storage_attrs.recharge_max,
                'min_runtime': storage_attrs.min_runtime,
                'warm_time': storage_attrs.warm_time
            })
        
        # Add generator attributes if available
        if generator_attrs:
            tech_data.update({
                'fuel': generator_attrs.fuel
            })
        
        return tech_data
    
    except Technologies.DoesNotExist:
        return None
    except TechnologyYears.DoesNotExist:
        return None

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

def copy_technologies_from_year0(technology_name, demand_year, scenario):
    scenario_obj = Scenarios.objects.get(title=scenario)
    try:
        technology_year0 = Technologies.objects.get(
            technology_name=technology_name,
            year=0
            )
    except Exception as e:
        # Assume it is the demand_year
        return None
    technology_new, created = Technologies.objects.get_or_create(
        technology_name=technology_name,
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
    # Remove the scenario from the year0 technology and add to the new
        technology_year0.scenarios.remove(scenario_obj)
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
            # Create a ScenariosTechnologies instance
            ScenariosTechnologies.objects.create(
                idscenarios=scenario_obj,
                idtechnologies=technology_new,
                merit_order=1,
                )
    return technology_new

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

def fetch_generators_parameter(demand_year, scenario, pmss_details, max_col):
    generators = {}
    dispatch_order = []
    re_order = ['Load']
    technologies_result = fetch_included_technologies_data(scenario)

    # Process the results
    fuel = None
    recharge_max = None
    recharge_loss = None
    discharge_max = None
    discharge_loss = None
    parasitic_loss = None
    for technology_row in technologies_result:      # Create a dictionary of Facilities objects
        name = technology_row.technology_name
        if name not in generators:
            generators[name] = {}
        if (technology_row.category == 'Generator'):
            try:
                generator_qs = Generatorattributes.objects.filter(
                    idtechnologies=technology_row,
                    year=demand_year,
                ).order_by('-year')
                generator = generator_qs[0]
                fuel = generator.fuel
                area = generator.area
            except Generatorattributes.DoesNotExist:
                # Handle the case where no matching generator object is found
                generator = None

        elif (technology_row.category == 'Storage'):
            try:
                storage_qs = Storageattributes.objects.filter(
                    idtechnologies=technology_row,
                    year=demand_year,
                ).order_by('-year')
                storage= storage_qs[0]
                recharge_max = storage.recharge_max
                recharge_loss = storage.recharge_loss
                discharge_max = storage.discharge_max
                discharge_loss = storage.discharge_loss
                parasitic_loss = storage.parasitic_loss
            except Storageattributes.DoesNotExist:
                # Handle the case where no matching storage object is found
                storage = None
            
        scenario_obj = Scenarios.objects.get(title=scenario)
        merit_order = ScenariosTechnologies.objects.filter(
            idscenarios=scenario_obj,
            idtechnologies=technology_row
            ).values_list('merit_order', flat=True)
        generators[name] = Facility(
            generator_name=name, category=technology_row.category, capacity=technology_row.capacity,
            constr=technology_row.technology_name,
            approach=technology_row.approach,
            capacity_max=technology_row.capacity_max, capacity_min=technology_row.capacity_min,
            multiplier=technology_row.mult,
            capacity_step=technology_row.capacity_step,
            recharge_max=recharge_max, recharge_loss=recharge_loss,
            min_runtime=0, warm_time=0,
            discharge_max=discharge_max,
            discharge_loss=discharge_loss, parasitic_loss=parasitic_loss,
            emissions=technology_row.emissions, initial=technology_row.initial, order=merit_order[0], 
            capex=technology_row.capex, fixed_om=technology_row.fom, variable_om=technology_row.vom,
            fuel=fuel, lifetime=technology_row.lifetime, area=area, disc_rate=technology_row.discount_rate,
            lcoe=technology_row.lcoe, lcoe_cfs=technology_row.lcoe_cf )

        renewable = technology_row.renewable
        category = technology_row.category
        if (renewable and category != 'Storage'):
            if (name not in re_order):
                re_order.append(name)
                
        dispatchable=technology_row.dispatchable
        if (dispatchable):
            if (name not in dispatch_order) and (name not in re_order):
                dispatch_order.append(name)
        capacity = technology_row.capacity
        if name not in pmss_details: # if not already included
            if (category == 'Storage'):
                pmss_details[name] = PM_Facility(name, name, capacity, 'S', -1, 1)
            else:
                typ = 'G'
                if renewable:
                    typ = 'R'
                pmss_details[name] = PM_Facility(name, name, capacity, typ, ++max_col, 1)
    return generators, dispatch_order, re_order, pmss_details

def getConstraints(scenario_id: int = None) -> Dict[str, Constraint]:
    """
    Creates a dictionary of Constraint objects from Technologies and StorageAttributes models.
    If scenario_id is provided, only returns constraints for technologies in that scenario.
    
    Args:
        scenario_id (int, optional): ID of the scenario to filter technologies
        
    Returns:
        Dict[str, Constraint]: Dictionary mapping technology signatures to their constraints
    """
    constraints = {}
    
    # Query base to get technologies with their storage attributes
    technologies = Technologies.objects.prefetch_related(
        Prefetch(
            'storageattributes_set',
            queryset=Storageattributes.objects.filter(year=0),
            to_attr='storage_attrs'
        )
    )
    
    # If scenario_id provided, filter technologies by scenario
    if scenario_id:
        technologies = technologies.filter(
            scenariostechnologies__idscenarios_id=scenario_id
        )
    
    for tech in technologies:
        # Get storage attributes if they exist
        storage_attrs = tech.storage_attrs[0] if hasattr(tech, 'storage_attrs') and tech.storage_attrs else None
        
        # Create constraint object
        constraint = Constraint(
            name=tech.technology_name,
            category=tech.category or '',
            capacity_min=tech.capacity_min or 0,
            capacity_max=tech.capacity_max or 1,
            rampup_max=storage_attrs.rampup_max if storage_attrs else 1,
            rampdown_max=storage_attrs.rampdown_max if storage_attrs else 1,
            recharge_max=storage_attrs.recharge_max if storage_attrs else 1,
            recharge_loss=storage_attrs.recharge_loss if storage_attrs else 0,
            discharge_max=storage_attrs.discharge_max if storage_attrs else 1,
            discharge_loss=storage_attrs.discharge_loss if storage_attrs else 0,
            parasitic_loss=storage_attrs.parasitic_loss if storage_attrs else 0,
            min_run_time=storage_attrs.min_runtime if storage_attrs else 0,
            warm_time=storage_attrs.warm_time if storage_attrs else 0
        )
        
        # Add to dictionary using technology name as key
        constraints[tech.technology_name] = constraint
    return constraints

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
        scenario_obj = Scenarios.objects.get(title=scenario)
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