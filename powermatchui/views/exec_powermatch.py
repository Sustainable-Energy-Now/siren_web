# run_powermatch.py
from ..database_operations import fetch_demand_data, fetch_full_generator_storage_data, fetch_settings_data
from datetime import datetime
from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.db.models import Max
from django.http import JsonResponse
from ..models import Analysis, Scenarios
from ..powermatch import pmcore as pm
from ..powermatch.pmcore import Facility, PM_Facility, powerMatch

def insert_data(i, sp_data, scenario_obj, Basis, Stage):
    for row in sp_data:
        if row[0] not in [' ', 'Load Analysis', 'Total incl. Carbon Cost', \
            'RE %age', 'Load Analysis', 'Load met', 'Shortfall', \
            'Total Load', 'RE %age of Total Load', 'Surplus', 'Static Variables', \
            'Carbon Price ($/tCO2e)', 'Lifetime (years)', 'Discount Rate']:
            results = [
                ('Capacity', row[0], row[1], 'MW'),
                ('To meet Load', row[0], row[2], 'MWh'),
                ('Cost', row[0], row[5], '$/yr'),
                ('LCOE', row[0], row[7], '$/MWh'),
                ('Emissions', row[0], row[8], 'tCO2e'),
                ('Emissions Cost', row[0], row[9], '$'),
                ('LCOE incl. Carbon Cost', row[0], row[10], '$/MWh'), 
                ('Max.', row[0], row[13], 'MWh'),
                ('Capital Cost', row[0], row[13], '$'),
                ('Lifetime Cost', row[0], row[14], '$'),
                ('Lifetime Emissions', row[0], row[14], 'tCO2e'),
                ('Lifetime Emissions Cost', row[0], row[14], '$'),
            ]
            for Heading, Component, Quantity, Units in results:
                try:
                    Decimal(Quantity)
                    pass
                except:
                    Quantity = 0
                Analysis.objects.create(
                    idscenarios=scenario_obj,
                    heading=Heading,
                    component=Component,
                    basis=Basis,
                    stage=Stage,
                    quantity=Quantity,
                    units=Units
                )

    # Write out Load Analysis statistics and Static Variables
    LoadAnalysis = [
        ('Load met', 'Load Analysis', sp_data[14][1], '%'),
        ('Load met', 'Load Analysis', sp_data[14][2], 'mWh'),
        ('Shortfall', 'Load Analysis', sp_data[15][1], '%'),
        ('Shortfall', 'Load Analysis', sp_data[15][2], 'mWh'),
        ('Total Load', 'Load Analysis', sp_data[16][2], 'mWh'),
        ('RE %age of Total Load', 'Load Analysis', sp_data[17][2], '%'),
        ('Surplus', 'Load Analysis', sp_data[19][2], '%'),
        ('Surplus', 'Load Analysis', sp_data[19][3], 'mWh')
    ]
    for Heading, Component, Quantity, Units in LoadAnalysis:
        try:
            Decimal(Quantity)
            pass
        except:
            Quantity = 0
        Analysis.objects.create(
            idscenarios=scenario_obj,
            heading=Heading,
            component=Component,
            basis=Basis,
            stage=Stage,
            quantity=Quantity,
            units=Units
        )

    # Insert Static Variables only in the first iteration (i.e., when i == 0)
    if i == 0:
        StaticVariables = [
            ('Carbon Price', 'Static Variables', sp_data[22][1], '$/tCO2e'),
            ('Lifetime', 'Static Variables', sp_data[23][1], 'years'), 
            ('Discount Rate', 'Static Variables', sp_data[24][1], '%'),
        ]
        for Heading, Component, Quantity, Units in StaticVariables:
            Analysis.objects.create(
                Scenario=Scenario,
                Heading=Heading,
                Component=Component,
                Basis=Basis,
                Stage=Stage,
                Quantity=Quantity,
                Units=Units
            )

def submit_powermatch(demand_year, scenario, option, iterations, updated_technologies):
    settings = fetch_settings_data()
    generators_result, column_names= fetch_full_generator_storage_data(demand_year)
    generators = {}
    dispatch_order = []
    re_order = ['Load']
    pmss_details = {}
    # Process the results
    for generator_row in generators_result:      # Create a dictionary to store the attributes by name
        attributes_by_name = {}
        for i, value in enumerate(generator_row):
            attributes_by_name[column_names[i]] = value

        name = attributes_by_name['technology_name']
        if name not in generators:
            generators[name] = {}
        generators[name] = Facility(
            generator_name=name, category=attributes_by_name['category'], capacity=attributes_by_name['capacity'],
            constr=attributes_by_name['technology_name'],
            capacity_max=attributes_by_name['capacity_max'], capacity_min=attributes_by_name['capacity_min'],
            recharge_max=attributes_by_name['recharge_max'], recharge_loss=attributes_by_name['recharge_loss'],
            min_runtime=attributes_by_name['min_runtime'], warm_time=attributes_by_name['warm_time'],
            discharge_max=attributes_by_name['discharge_max'],
            discharge_loss=attributes_by_name['discharge_loss'], parasitic_loss=attributes_by_name['parasitic_loss'],
            emissions=attributes_by_name['emissions'], initial=attributes_by_name['initial'], order=attributes_by_name['merit_order'], 
            capex=attributes_by_name['capex'], fixed_om=attributes_by_name['FOM'], variable_om=attributes_by_name['VOM'],
            fuel=attributes_by_name['fuel'], lifetime=attributes_by_name['lifetime'], disc_rate=attributes_by_name['discount_rate'],
            lcoe=attributes_by_name['lcoe'], lcoe_cfs=attributes_by_name['lcoe_cf'] )

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
        if (category == 'Storage'):
            pmss_details[name] = PM_Facility(name, name, capacity, 'S', -1, 1)
    else:
        pmss_details[name].capacity = capacity
    # Call the static method directly
    pmss_data, pmss_details, dispatch_order, re_order = fetch_demand_data(demand_year)
    pm_data_file = 'G:/Shared drives/SEN Modelling/modelling/SWIS/Powermatch_data_actual.xlsx'
    data_file = 'Powermatch_results_actual.xlsx'
    for i in range(iterations):
        # 0 Facility
        # 1 Capacity (Gen, MW Stor, MWh)  
        # 2 To meet Load (MWh)
        # 3 Subtotal (MWh)
        # 4 CF
        # 5 Cost ($/yr)
        # 6 LCOG Cost ($/MWh)
        # 7 LCOE Cost ($/MWh)
        # 8 Emissions (tCO2e)
        # 9 Emissions Cost
        # 10 LCOE incl. Carbon Cost
        # 11 Max. MWH
        # 12 Max. Balance
        # 13 Capital Cost
        # 14 Lifetime Cost
        # 15 Lifetime Emissions
        # 16 Lifetime Emissions Cost
        # 17 Reference LCOE
        # 18 Reference CF

        sp_data, headers, sp_pts = powerMatch.doDispatch(settings, demand_year, option, pmss_details, pmss_data, generators, re_order, 
            dispatch_order, pm_data_file, data_file, title=None)
        
        if option == 'B':
            current_datetime = datetime.now()
            Stage = current_datetime.strftime('%m-%d %H:%M:%S')
            Basis = 'Optimisation'
            try:
                scenario_obj = Scenarios.objects.get(title=scenario)
                # Use the scenario object here
            except Scenarios.DoesNotExist:
                # Handle the case where the scenario with the given title does not exist
                pass
            insert_data(i, sp_data, scenario_obj, Basis, Stage)
            # Adjust capacity by step value
            for key, value in pmss_details.items():
                if key in updated_technologies:
                    pmss_details[key] = PM_Facility(value.name, value.name, value.capacity + updated_technologies[key], 'R', value.col, value.multiplier)

    return sp_data, headers, sp_pts

def start_powermatch_task(request):
    # Start the Celery task asynchronously
    task = run_powermatch_task.delay(settings, generators, demand_year, option, pmss_details, pmss_data, re_order, dispatch_order, pm_data_file, data_file)
    return JsonResponse({'task_id': task.id})

def get_task_progress(request, task_id):
    # Get progress of the Celery task
    task = run_powermatch_task.AsyncResult(task_id)
    if task.state == 'SUCCESS':
        return JsonResponse({'progress': 100, 'message': 'Task completed successfully'})
    elif task.state == 'FAILURE':
        return JsonResponse({'progress': 0, 'message': 'Task failed'})
    else:
        # Get task progress from task.info dictionary (if available)
        progress = task.info.get('progress', 0)
        message = task.info.get('message', 'Task in progress')
        return JsonResponse({'progress': progress, 'message': message})
