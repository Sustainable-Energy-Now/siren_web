# run_powermatch.py
from datetime import datetime
from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.db.models import Max
from django.http import JsonResponse
from siren_web.database_operations import fetch_all_settings_data, fetch_included_technologies_data, \
    fetch_supplyfactors_data
from siren_web.models import Analysis, Generatorattributes, Scenarios, ScenariosSettings, ScenariosTechnologies, Storageattributes
from siren_web.siren import pmcore as pm
from siren_web.siren.pmcore import Facility, PM_Facility, powerMatch

def insert_data(i, sp_data, scenario_obj, variation, Stage):
    for count, row in enumerate(sp_data):
        if not row[0]:
            pass
        if row[0] not in [' ', 'Additional Underlying Load', 'Carbon Price ($/tCO2e)', 'Load Analysis', 'Total incl. Carbon Cost', 'RE %age', \
            'Load Analysis', 'Load met', 'Shortfall', 'Total Load', 'RE %age of Total Load', 'Static Variables', \
            'Storage %age', 'Storage Losses', 'Surplus', 'Largest Shortfall', 'Lifetime (years)', 'Discount Rate']:
            results = [
                ('Capacity', row[0], row[1], 'MW'),
                ('To Meet Load', row[0], row[2], 'MWh'),
                ('CF', row[0], row[4], '%'),
                ('Cost', row[0], row[5], '$/yr'),
                ('LCOG Cost', row[0], row[6], '$/MWh'),
                ('LCOE Cost', row[0], row[7], '$/MWh'),
                ('Emissions', row[0], row[8], 'tCO2e'),
                ('Emissions Cost', row[0], row[9], '$'),
                ('LCOE with CO2 Cost', row[0], row[10], '$/MWh'), 
                ('Max.', row[0], row[11], 'MWh'),
                ('Capital Cost', row[0], row[13], '$'),
                ('Lifetime Cost', row[0], row[14], '$'),
                ('Lifetime Emissions', row[0], row[15], 'tCO2e'),
                ('Lifetime Emissions Cost', row[0], row[16], '$'),
            ]
            for Heading, Component, Quantity, Units in results:
                try:
                    if isinstance(Quantity, str):
                        Quantity = Quantity.replace('%', '')
                        float(Quantity)
                    pass
                except:
                    Quantity = 0
                Analysis.objects.create(
                    idscenarios=scenario_obj,
                    heading=Heading,
                    component=Component,
                    variation=variation,
                    stage=Stage,
                    quantity=Quantity,
                    units=Units
                )
        if row[0] == 'Load Analysis':
            LA_index = count + 1
        if row[0] == 'Static Variables':
            SV_index = count + 1
    # Write out Load Analysis statistics and Static Variables

    LoadAnalysis = [
        ('% Load met', 'Load Analysis', sp_data[LA_index][1], '%'),
        ('Load met', 'Load Analysis', sp_data[LA_index][2], 'mWh'),
        ('% Shortfall', 'Load Analysis', sp_data[LA_index + 1][1], '%'),
        ('Shortfall', 'Load Analysis', sp_data[LA_index + 1][2], 'mWh'),
        ('Total Load', 'Load Analysis', sp_data[LA_index + 2][2], 'mWh'),
        ('RE %age of Total Load', 'Load Analysis', sp_data[LA_index + 3][1], '%'),
        ('% Surplus', 'Load Analysis', sp_data[LA_index + 5][1], '%'),
        ('Surplus', 'Load Analysis', sp_data[LA_index + 5][3], 'mWh'),
        # ('Largest Shortfall', 'Load Analysis', sp_data[LA_index + 6][3], 'mWh')
    ]
    for Heading, Component, Quantity, Units in LoadAnalysis:
        try:
            if isinstance(Quantity, str):
                Quantity = Quantity.replace('%', '')
                float(Quantity)
            pass
        except:
            Quantity = 0
        Analysis.objects.create(
            idscenarios=scenario_obj,
            heading=Heading,
            component=Component,
            variation=variation,
            stage=Stage,
            quantity=Quantity,
            units=Units
        )

    # If the first iteration insert Static Variables into the ScenariosSettings table
    if i == 0:
        
        StaticVariables = [
            ('carbon_price', sp_data[SV_index][1], '$/tCO2e'),
            ('discount_rate', sp_data[SV_index + 2][1], '%'),
        ]
        for Parameter, Value, Units in StaticVariables:
            ScenariosSettings.objects.create(
                idscenarios=scenario_obj,
                sw_context='Powermatch',
                parameter=Parameter,
                value=Value,
                units=Units,
            )

def submit_powermatch(demand_year, scenario, 
                      option, stages, variation_inst, save_data):
    settings = fetch_all_settings_data()
    pmss_data, pmss_details, max_col = \
    fetch_supplyfactors_data(demand_year)
    
    technologies_result = fetch_included_technologies_data(scenario)
    
    generators = {}
    dispatch_order = []
    re_order = ['Load']

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
            capacity_max=technology_row.capacity_max, capacity_min=technology_row.capacity_min,
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

    pm_data_file = 'G:/Shared drives/SEN Modelling/modelling/SWIS/Powermatch_data_actual.xlsx'
    data_file = 'Powermatch_results_actual.xlsx'
    for i in range(stages):
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
                
        # If dimension is capacity then adjust capacity by step value each iteration
        if variation_inst:
            technology = variation_inst.idtechnologies
            dimension = variation_inst.dimension
            step = variation_inst.step
            idtechnologies = variation_inst.idtechnologies
            technology_name = idtechnologies.technology_name
            capex_step = 0
            lifetime_step = 0
            if (dimension == 'capacity'):
                pmss_details[technology_name] = PM_Facility(
                    pmss_details[technology_name].name, 
                    pmss_details[technology_name].name, 
                    pmss_details[technology_name].capacity + step, 'R', 
                    pmss_details[technology_name].col, 
                    pmss_details[technology_name].multiplier
                    )
            elif (dimension == 'capex'):
                capex_step = technology_row.capex + step
            elif (dimension == 'lifetime'):
                lifetime_step = technology_row.lifetime + step
                
            generators[technology_name] = Facility(
                generator_name=name, category=technology_row.category, capacity=technology_row.capacity,
                constr=technology_row.technology_name,
                capacity_max=technology_row.capacity_max, capacity_min=technology_row.capacity_min,
                recharge_max=recharge_max, recharge_loss=recharge_loss,
                min_runtime=0, warm_time=0,
                discharge_max=discharge_max,
                discharge_loss=discharge_loss, parasitic_loss=parasitic_loss,
                emissions=technology_row.emissions, initial=technology_row.initial, order=merit_order[0], 
                capex=technology_row.capex + capex_step, fixed_om=technology_row.fom, variable_om=technology_row.vom,
                fuel=fuel, lifetime=technology_row.lifetime + lifetime_step, area=area, disc_rate=technology_row.discount_rate,
                lcoe=technology_row.lcoe, lcoe_cfs=technology_row.lcoe_cf )

        sp_data, headers, sp_pts = powerMatch.doDispatch(settings, demand_year, option, pmss_details, pmss_data, generators, re_order, 
            dispatch_order, pm_data_file, data_file, title=None)
        # if option == 'O':
        #     message = ex.optClicked(load_year, option, pmss_details, 
        #     pmss_data, re_order, dispatch_order, OptParms, optimisation, None, None)
        # If the detailed option was selected then sp_data is an excel work book to be downloaded.
        if option != 'D':
            if variation_inst:
                variation = variation_inst.variation_name
                Stage = i + 1
            else:
                variation = 'Baseline'
                Stage = 0
            # current_datetime = datetime.now()
            # Stage = current_datetime.strftime('%m-%d %H:%M:%S')

            try:
                scenario_obj = Scenarios.objects.get(title=scenario)
                # Use the scenario object here
            except Scenarios.DoesNotExist:
                # Handle the case where the scenario with the given title does not exist
                pass
            if save_data:
                insert_data(i, sp_data, scenario_obj, variation, Stage)

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
