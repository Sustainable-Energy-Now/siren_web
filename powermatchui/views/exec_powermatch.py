# run_powermatch.py
from django.contrib.auth.decorators import login_required
from siren_web.database_operations import fetch_all_config_data, fetch_module_settings_data, fetch_scenario_settings_data, \
    fetch_technology_attributes, fetch_supplyfactors_data
from siren_web.models import Analysis, ScenariosSettings
from .balance_grid_load import Technology, PowerMatchProcessor

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

def submit_powermatch(request, demand_year, scenario, 
                      option, stages, variation_inst, save_data):
    config = fetch_all_config_data(request)
    scenario_settings = fetch_scenario_settings_data(scenario)
    if not scenario_settings:
        scenario_settings = fetch_module_settings_data('Powermatch')
    pmss_data = \
        fetch_supplyfactors_data(demand_year, scenario)
    pmss_details = \
        fetch_technology_attributes(demand_year, scenario)
    
    for i in range(stages):
        # 0 Technology
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
            technology_name = technology.technology_name
            capex_step = 0
            lifetime_step = 0
            
            if dimension == 'capacity':
                pmss_details[technology_name] = Technology(
                    pmss_details[technology_name].name, 
                    pmss_details[technology_name].name, 
                    pmss_details[technology_name].capacity + step, 'R', 
                    pmss_details[technology_name].col, 
                    pmss_details[technology_name].multiplier
                )
            elif dimension == 'capex':
                capex_step = step
            elif dimension == 'lifetime':
                lifetime_step = step
                
            # Update generator with variation if it affects this technology
            if technology_name in pmss_details:
                original_facility = pmss_details[technology_name]
                pmss_details[technology_name] = Technology(
                    generator_name=original_facility.generator_name,
                    category=original_facility.category,
                    capacity=original_facility.capacity,
                    capacity_max=original_facility.capacity_max,
                    capacity_min=original_facility.capacity_min,
                    recharge_max=original_facility.recharge_max,
                    recharge_loss=original_facility.recharge_loss,
                    min_runtime=original_facility.min_runtime,
                    warm_time=original_facility.warm_time,
                    discharge_max=original_facility.discharge_max,
                    discharge_loss=original_facility.discharge_loss,
                    parasitic_loss=original_facility.parasitic_loss,
                    emissions=original_facility.emissions,
                    initial=original_facility.initial,
                    order=original_facility.order,
                    capex=original_facility.capex + capex_step,
                    fixed_om=original_facility.fixed_om,
                    variable_om=original_facility.variable_om,
                    fuel=original_facility.fuel,
                    lifetime=original_facility.lifetime + lifetime_step,
                    area=original_facility.area,
                    lcoe=original_facility.lcoe,
                    lcoe_cfs=original_facility.lcoe_cfs
                )

        pm = PowerMatchProcessor(scenario_settings)
        if option == 'D':
            action = 'Detail'
        else:
            action = 'Summary'
            
        # sp_data, corr_data, headers, sp_pts = pm.doDispatch(
        #     demand_year, option, action, pmss_details, pmss_data
        # )
        dispatch_results = pm.doDispatch(
            demand_year, option, action, pmss_details, pmss_data
        )
        # Extract data from DispatchResults object
        sp_data = dispatch_results.summary_data
        metadata = dispatch_results.metadata
        hourly_data = dispatch_results.hourly_data
        # Access results
        print(f"System LCOE: ${metadata['system_lcoe']:.2f}/MWh")
        print(f"Renewable percentage: {metadata['renewable_pct']*100:.1f}%")
        print(f"Load met: {metadata['load_met_pct']*100:.1f}%")
            
        # Work with hourly data (if available)
        if hourly_data is not None:
            # Example: Plot first week (hours 0-167)
            print(f"Hourly data available for {hourly_data.shape[0]} hours, {hourly_data.shape[1]} columns")
 
        return sp_data
    
        # Save results if not detailed option
    #     if option != 'D':
    #         if variation_inst:
    #             variation = variation_inst.variation_name
    #             Stage = i + 1
    #         else:
    #             variation = 'Baseline'
    #             Stage = 0

    #         if save_data:
    #             insert_data(i, sp_data, scenario_obj, variation, Stage)

    # return sp_data, headers, sp_pts
