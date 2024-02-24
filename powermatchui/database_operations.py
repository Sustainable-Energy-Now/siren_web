# In powermatchui database operations
from django.db import connection
from django.http import HttpResponse
from .models import Constraints, Demand, Scenarios, Settings, Technologies, Zones
from .powermatch.pmcore import Constraint, Facility, PM_Facility, Optimisation

def fetch_constraints_data(request):
    # Check if constraints are already stored in session
    if 'constraints' in request.session:
        return request.session['constraints']
    try:
        constraints = {}
        constraints_query = Constraints.objects.all()
        for constraint_row in constraints_query:
            constraint_name = constraint_row.constraintname
            if constraint_name not in constraints:
                constraints[constraint_name] = {}
            constraints[constraint_name] = Constraint(
                constraint_name, category=constraint_row.category,
                capacity_max=constraint_row.capacitymax, capacity_min=constraint_row.capacitymin,
                discharge_loss=constraint_row.dischargeloss, discharge_max=constraint_row.dischargemax,
                parasitic_loss=constraint_row.parasiticloss, rampdown_max=constraint_row.rampdownmax,
                rampup_max=constraint_row.rampupmax, recharge_loss=constraint_row.rechargeloss,
                recharge_max=constraint_row.rechargemax, min_run_time=0, warm_time=0
                    )
    except Exception as e:
        # Handle any errors that occur during the database query
        return None
    
    # Store constraints data in session
    request.session['constraints'] = constraints
    return constraints

def fetch_demand_data(request, load_year):
    # Check if demand is already stored in session
    if 'pmss_data' in request.session:
        return request.session['pmss_data'], request.session['pmss_details']
    try:
        # Read demand table using Django ORM
        demand_query = Demand.objects.filter(
        ).select_related(
            'constraintid'  # Perform join with Constraints
        ).order_by(
            'col', 'hour'  # Order the results by col and hour
        )
        # Create a dictionary of Demand from the model 
        pmss_data = {}
        pmss_details = {} # contains name, generator, capacity, fac_type, col, multiplier
        pmss_details['Load'] = PM_Facility('Load', 'Load', 1, 'L', 0, 1)
        for demand_row in demand_query:
            name = demand_row.constraintid.constraintname
            constraintid = demand_row.constraintid.id
            col = demand_row.col
            load = demand_row.load
            if col not in pmss_data:
                pmss_data[col] = []
            pmss_data[col].append(load)
            if (name != 'Load'):
                if name not in pmss_details: # type: ignore
                    try:            
                        id_scenarios_value = 1  # Example value for idScenarios
                        capacity_obj = Zones.objects.filter(idscenarios=id_scenarios_value, 
                            constraintid=constraintid).first()
                        capacity = capacity_obj.capacity if capacity_obj else 0  # Accessing the capacity attribute if capacity_obj is not None
                    except Exception as e:
                        capacity = 0
                    pmss_details[name] = PM_Facility(name, name, capacity, 'R', col, 1)
    except Exception as e:
        # Handle any errors that occur during the database query
        return HttpResponse(f"Error fetching demand data: {e}", status=500), None
    
    # Read Technologies from the database.    
 
    technologies_result, column_names = fetch_full_generator_storage_data(request, load_year)
    
    # Create a dictionary of technologies and their constraints for the chosen year from the dataframe in cache.
    # exclude any where merit_order > 99
    generators = {}
    dispatch_order = []
    re_order = ['Load']

    for technology_row in technologies_result:
        # Create a dictionary to store the attributes by name
        attributes_by_name = {}
        for i, value in enumerate(technology_row):
            attributes_by_name[column_names[i]] = value
        order = attributes_by_name['merit_order']
        if (order <= 99):
            name = attributes_by_name['technology_name']
            if (name not in generators):
                generators[name] = Facility(
                    generator_name=name, capacity=attributes_by_name['capacity'], constr=name,
                    emissions=attributes_by_name['emissions'], initial=attributes_by_name['initial'], order=order, 
                    capex=attributes_by_name['capex'], fixed_om=attributes_by_name['FOM'], variable_om=attributes_by_name['VOM'],
                    fuel=attributes_by_name['fuel'], lifetime=attributes_by_name['lifetime'], disc_rate=attributes_by_name['discount_rate'],
                    lcoe=None, lcoe_cfs=None )
            dispatchable=attributes_by_name['dispatchable']
            if (dispatchable):
                if (name not in dispatch_order):
                    dispatch_order.append(name)
            renewable = attributes_by_name['renewable']
            category = attributes_by_name['category']
            if (renewable and category != 'Storage'):
                if (name not in re_order):
                    re_order.append(name)
            capacity = attributes_by_name['capacity']
            if name not in pmss_details: # type: ignore
                pmss_details[name] = PM_Facility(name, name, capacity, 'S', -1, 1)
            else:
                pmss_details[name].capacity = capacity
   
    # Store demand data in session
    return pmss_data, pmss_details, dispatch_order, re_order

def fetch_full_generator_storage_data(request, load_year):
    # Define the SQL query
    generators_query = \
    f"""
        WITH cte AS (
        SELECT t.*,
        s.capacity_max, s.capacity_min, s.discharge_loss,
        s.discharge_max, s.parasitic_loss, s.rampdown_max,
        s.rampup_max, s.recharge_loss, s.recharge_max,
        g.initial, g.fuel,
        ROW_NUMBER() OVER (PARTITION BY t.technology_name ORDER BY t.merit_order, t.year DESC) AS row_num
        FROM senas316_pmdata.Technologies t
        LEFT JOIN senas316_pmdata.StorageAttributes s ON t.idtechnologies = s.idtechnologies 
            AND t.category = 'Storage' AND t.year = s.year
        LEFT JOIN senas316_pmdata.GeneratorAttributes g ON t.idtechnologies = g.idtechnologies 
            AND t.category = 'Generator' AND t.year = g.year
        WHERE t.year IN (0, {load_year})
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
                print("No results found.")
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
    
def fetch_merit_order_technologies(load_year):
    candidate_technologies = fetch_generation_storage_data(load_year)
    merit_order_data = {}
    excluded_resources_data = {}
    # Create dictionaries with idtechnologies as keys and names as values
    seen_technologies = set()
    for tech in candidate_technologies:
    # Filter out duplicate technology_name rows, keeping only the one with year = load_year
        if candidate_technologies[tech][0] not in seen_technologies:
            if (candidate_technologies[tech][1] <= 99):
                merit_order_data[tech] = [candidate_technologies[tech][0], get_emission_color(candidate_technologies[tech][2])]
            else:
                excluded_resources_data[tech] = [candidate_technologies[tech][0], get_emission_color(candidate_technologies[tech][2])]
            seen_technologies.add(candidate_technologies[tech][0])
    return merit_order_data, excluded_resources_data

def fetch_generation_storage_data(load_year):
    # Filter technologies based on merit_order conditions
    candidate_technologies = Technologies.objects.filter(
        year__in=[0, load_year],
        category__in=['Generator', 'Storage']  # Use double underscores for related field lookups
    ).order_by('merit_order', '-year')
    seen_technologies = set()
    technologies = {}
    for tech in candidate_technologies:
    # Filter out duplicate technology_name rows, keeping only the one with year = load_year
        if tech.idtechnologies not in seen_technologies:
            technologies[tech.idtechnologies] = [tech.technology_name, tech.merit_order, tech.emissions]
            seen_technologies.add(tech.idtechnologies)
    return technologies

def fetch_included_technologies_data(load_year):
    # Filter technologies based on merit_order conditions
    candidate_technologies = Technologies.objects.filter(
        year__in=[0, load_year],
        category__in=['Generator', 'Storage'],  # Use double underscores for related field lookups
        merit_order__lte=99
    ).order_by('merit_order', '-year')
    seen_technologies = set()
    technologies = {}
    for tech in candidate_technologies:
    # Filter out duplicate technology_name rows, keeping only the one with year = load_year
        if tech.technology_name not in seen_technologies:
            technologies[str(tech.idtechnologies)] = [tech.technology_name, tech.capacity, tech.mult]
            seen_technologies.add(tech.technology_name)
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
    
def fetch_settings_data(request):
    # Check if settings are already stored in session
    if 'settings' in request.session:
        return request.session['settings']
    try:
        settings = {}
        settings_query = Settings.objects.all()
        for setting in settings_query:
            context = setting.context
            parameter = setting.parameter
            value = setting.value
            if context not in settings:
                settings[context] = {}
            settings[context][parameter] = value
    except Exception as e:
        # Handle any errors that occur during the database query
        return None
    
    # Store settings data in session
    request.session['settings'] = settings
    return settings