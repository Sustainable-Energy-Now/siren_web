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
        return HttpResponse(f"Error fetching demand data: {e}", status=500)
    
    # Store demand data in session
    request.session['pmss_data'] = pmss_data
    request.session['pmss_details'] = pmss_details
    return pmss_data, pmss_details

def fetch_technologies_data(request, load_year):
    # Check if generators are already stored in session
    if 'generators' in request.session:
        return request.session['generators'], request.session['dispatch_order'], request.session['re_order']
    try:
        # Define the SQL query
        generators_query = \
        f"""
            WITH cte AS (
            SELECT t.*, 
            s.capacity_max, s.capacity_min, s.discharge_loss,
            s.discharge_max, s.parasitic_loss, s.rampdown_max,
            s.rampup_max, s.recharge_loss, s.recharge_max,
            g.capacity, g.emissions,
            g.initial,
            g.mult,
            g.fuel,
            ROW_NUMBER() OVER (PARTITION BY t.technology_name ORDER BY t.year DESC) AS row_num
            FROM senas316_pmdata.Technologies t
            LEFT JOIN senas316_pmdata.StorageAttributes s ON t.idtechnologies = s.idtechnologies 
                AND t.function = 'storage' AND t.year = s.year
            LEFT JOIN senas316_pmdata.GeneratorAttributes g ON t.idtechnologies = g.idtechnologies 
                AND t.function = 'generator' AND t.year = g.year
            WHERE t.year IN (0, {load_year})
            )
            SELECT *
            FROM cte
            WHERE row_num = 1;
        """
        # Execute the SQL query
        with connection.cursor() as cursor:
            cursor.execute(generators_query)
            # Fetch the results
            generators_result = cursor.fetchall()
            column_names = [desc[0] for desc in cursor.description]
                    
    except Exception as e:
        print("Error executing query:", e)
        # Get the column names
    try:
        # Get the column names
        generators = {}
        dispatch_order = []
        re_order = ['Load']
        pmss_details = {}
        # Process the results
        for generator_row in generators_result:
            # Create a dictionary to store the attributes by name
            attributes_by_name = {}
            for i, value in enumerate(generator_row):
                attributes_by_name[column_names[i]] = value

            name = attributes_by_name['Name']
            if name not in generators:
                generators[name] = {}
            generators[name] = Facility(
                generator_name=name, capacity=attributes_by_name['Capacity'], constr=attributes_by_name['ConstraintName'],
                emissions=attributes_by_name['Emissions'], initial=attributes_by_name['Initial'], order=attributes_by_name['Ord'], 
                capex=attributes_by_name['Capex'], fixed_om=attributes_by_name['FOM'], variable_om=attributes_by_name['VOM'],
                fuel=attributes_by_name['Fuel'], lifetime=attributes_by_name['Lifetime'], disc_rate=attributes_by_name['DiscountRate'],
                lcoe=None, lcoe_cfs=None )
 
            dispatchable=attributes_by_name['Dispatchable']
            if (dispatchable):
                if (name not in dispatch_order):
                    dispatch_order.append(name)
            renewable = attributes_by_name['Renewable']
            category = attributes_by_name['Category']
            if (renewable and category != 'Storage'):
                if (name not in re_order):
                    re_order.append(name)
            capacity = attributes_by_name['Capacity']
            if name not in pmss_details: # type: ignore
                pmss_details[name] = PM_Facility(name, name, capacity, 'S', -1, 1)
            else:
                pmss_details[name].capacity = capacity
    except Exception as e:
        # Handle any errors that occur during the database query
        return HttpResponse(f"Error fetching generators data: {e}", status=500), None, None
    
    # Store generators data in session
    request.session['generators'] = generators
    request.session['dispatch_order'] = dispatch_order
    request.session['re_order'] = re_order
    return generators, dispatch_order, re_order

def fetch_dispatchables_data(request, load_year):
    dispatchables = Technologies.objects.filter(dispatchable=True, year=load_year)
    return dispatchables

def fetch_merit_order_data(load_year):
    merit_order_data = Technologies.objects.filter(dispatchable=True, year=load_year)
    return merit_order_data

def fetch_excluded_resources_data(load_year):
    excluded_resources_data = Technologies.objects.filter(dispatchable=True, year=load_year)
    return excluded_resources_data

def fetch_generation_storage_data(load_year):
    # Filter technologies based on dispatchable and merit_order conditions
    candidate_technologies = Technologies.objects.filter(
        year__in=[0, load_year],
        function__in=['Generation', 'Storage']  # Use double underscores for related field lookups
    ).order_by('merit_order', '-year')

    merit_order_data = {}
    excluded_resources_data = {}
    seen_technologies = set()

    # Create dictionaries with idtechnologies as keys and names as values
    for tech in candidate_technologies:
    # Filter out duplicate technology_name rows, keeping only the one with year = load_year
        if tech.idtechnologies not in seen_technologies:
            if (tech.merit_order <= 99):
                merit_order_data[tech.idtechnologies] = tech.technology_name
            else:
                excluded_resources_data[tech.idtechnologies] = tech.technology_name
            seen_technologies.add(tech.idtechnologies)
    return merit_order_data, excluded_resources_data

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